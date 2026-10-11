"""Retry policy: 429, 5xx, lost connections, Retry-After, backoff."""

import pytest
import requests

from collibra_toolkit import (
    CollibraAuthError,
    CollibraClient,
    CollibraError,
    CollibraHTTPError,
    CollibraNotFound,
    CollibraRateLimitError,
    CollibraServerError,
)
from tests.support.fakes import FakeResp, FakeSession, RoutedSession, make_client
from collibra_toolkit.client.retry import parse_retry_after


def retrying(*responses, **kw):
    """Client with a recording sleeper and no jitter, so waits are exact."""
    slept = []
    sess = FakeSession(*responses, **kw)
    client = CollibraClient("https://x.collibra.com", username="u", password="p", session=sess,
                            sleep=slept.append, jitter=lambda d: d)
    return client, sess, slept


def test_429_is_retried_and_retry_after_is_honoured():
    first = FakeResp(429, b"slow down", headers={"Retry-After": "2"})
    c, sess, slept = retrying(first, FakeResp(200, payload={"ok": 1}))
    assert c.get_json("/x") == {"ok": 1}
    assert slept == [2.0] and len(sess.calls) == 2 and first.closed


def test_backoff_is_exponential_and_capped_then_a_typed_error():
    c, sess, slept = retrying(FakeResp(503, b"down"))
    with pytest.raises(CollibraServerError) as info:
        c.get_json("/x")
    assert info.value.status_code == 503
    assert slept == [0.5, 1.0, 2.0, 4.0] and len(sess.calls) == 5      # 1 try + 4 retries

    c, _, slept = retrying(FakeResp(429, b"", headers={"Retry-After": "9999"}))
    with pytest.raises(CollibraRateLimitError) as info:
        c.get_json("/x")
    assert info.value.retry_after == 9999.0
    assert max(slept) == 60.0                                          # never sleeps longer than max_wait


def test_5xx_is_retried_for_safe_methods_only_but_429_for_all():
    c, sess, slept = retrying(FakeResp(503, b"down"))
    with pytest.raises(CollibraServerError):
        c.request("POST", "/x")
    assert len(sess.calls) == 1 and slept == []                       # a POST may have been processed: not repeated

    c, sess, slept = retrying(FakeResp(429, b"", headers={"Retry-After": "1"}), FakeResp(200, payload={}))
    c.request("POST", "/x")
    assert len(sess.calls) == 2                                       # 429 means it was not processed: safe

    c, sess, _ = retrying(FakeResp(500, b"err"), FakeResp(200, payload={}))
    c.request("DELETE", "/x")
    assert len(sess.calls) == 2


def test_client_errors_are_never_retried():
    for status in (400, 403, 404):
        c, sess, slept = retrying(FakeResp(status, b"no"))
        with pytest.raises(CollibraHTTPError):
            c.get_json("/x")
        assert len(sess.calls) == 1 and slept == []


def test_lost_connections_are_retried_but_ssl_errors_are_not():
    c, sess, slept = retrying(requests.ConnectionError("reset"), requests.Timeout("slow"), FakeResp(200, payload={"ok": 1}))
    assert c.get_json("/x") == {"ok": 1} and slept == [0.5, 1.0]

    c, sess, slept = retrying(requests.exceptions.SSLError("bad cert"), FakeResp(200, payload={}))
    with pytest.raises(CollibraError, match="SSLError"):
        c.get_json("/x")
    assert len(sess.calls) == 1 and slept == []

    c, sess, _ = retrying(requests.ConnectionError("reset"), FakeResp(200, payload={}))
    with pytest.raises(CollibraError):
        c.request("POST", "/x")                                         # not repeated: it may have been sent
    assert len(sess.calls) == 1


def test_parse_retry_after_formats():
    assert parse_retry_after("5") == 5.0
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0    # a date in the past means: retry now
    assert parse_retry_after("garbage") is None and parse_retry_after(None) is None

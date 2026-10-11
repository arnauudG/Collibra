"""The request path: URL building, defaults, typed HTTP errors."""

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


def test_url_building_and_default_options():
    c, sess = make_client(FakeResp(payload={"ok": 1}))
    assert c.get_json("/communities", {"limit": 2}) == {"ok": 1}
    method, url, kw = sess.calls[0]
    assert (method, url) == ("GET", "https://x.collibra.com/rest/2.0/communities")
    assert kw["params"] == {"limit": 2} and kw["allow_redirects"] and kw["timeout"] == 60


@pytest.mark.parametrize(
    "status,exc",
    [(401, CollibraAuthError), (403, CollibraAuthError), (404, CollibraNotFound), (418, CollibraHTTPError)],
)
def test_http_errors_are_typed(status, exc):
    c, _ = make_client(FakeResp(status, b"nope"))
    with pytest.raises(exc) as info:
        c.request("GET", "/x")
    assert info.value.status_code == status and "nope" in str(info.value)


def test_network_errors_do_not_leak_urls():
    c, _ = make_client(FakeResp(), raises=requests.ConnectionError("https://bucket/x?X-Amz-Signature=secret"))
    with pytest.raises(CollibraError) as info:
        c.request("GET", "/x")
    assert "secret" not in str(info.value) and "ConnectionError" in str(info.value)

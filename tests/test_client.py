import pytest
import requests
from fakes import FakeResp, FakeSession

from collibra_toolkit import (
    CollibraAuthError,
    CollibraClient,
    CollibraError,
    CollibraHTTPError,
    CollibraNotFound,
)


def make(*responses, **kw):
    sess = FakeSession(*responses, **kw)
    return CollibraClient("https://x.collibra.com/", username="u", password="p", session=sess, sleep=lambda s: None), sess


def test_requires_credentials():
    with pytest.raises(CollibraError):
        CollibraClient("https://x")


def test_auth_modes():
    s = FakeSession(FakeResp())
    CollibraClient("https://x", token="t", session=s)
    assert s.headers["Authorization"] == "Bearer t"
    s = FakeSession(FakeResp())
    CollibraClient("https://x", username="u", password="p", session=s)
    assert s.auth == ("u", "p")


def test_from_env():
    env = {"COLLIBRA_URL": "https://x", "COLLIBRA_TOKEN": "t"}
    assert CollibraClient.from_env(env, session=FakeSession(FakeResp())).base_url == "https://x"
    with pytest.raises(CollibraError, match="COLLIBRA_URL"):
        CollibraClient.from_env({})


def test_url_building_and_default_options():
    c, sess = make(FakeResp(payload={"ok": 1}))
    assert c.get_json("/communities", {"limit": 2}) == {"ok": 1}
    method, url, kw = sess.calls[0]
    assert (method, url) == ("GET", "https://x.collibra.com/rest/2.0/communities")
    assert kw["params"] == {"limit": 2} and kw["allow_redirects"] and kw["timeout"] == 60


@pytest.mark.parametrize(
    "status,exc",
    [(401, CollibraAuthError), (403, CollibraAuthError), (404, CollibraNotFound), (418, CollibraHTTPError)],
)
def test_http_errors_are_typed(status, exc):
    c, _ = make(FakeResp(status, b"nope"))
    with pytest.raises(exc) as info:
        c.request("GET", "/x")
    assert info.value.status_code == status and "nope" in str(info.value)


def test_network_errors_do_not_leak_urls():
    c, _ = make(FakeResp(), raises=requests.ConnectionError("https://bucket/x?X-Amz-Signature=secret"))
    with pytest.raises(CollibraError) as info:
        c.request("GET", "/x")
    assert "secret" not in str(info.value) and "ConnectionError" in str(info.value)


def page(items, total=None, limit=2):
    return FakeResp(payload={"results": items, "total": total, "limit": limit})


def test_paginate_follows_offsets_until_total():
    c, sess = make(page([1, 2], total=5), page([3, 4], total=5), page([5], total=5))
    assert list(c.paginate("/things", page_size=2)) == [1, 2, 3, 4, 5]
    assert [call[2]["params"]["offset"] for call in sess.calls] == [0, 2, 4]


def test_paginate_without_total_stops_on_short_page():
    c, sess = make(page([1, 2]), page([3]))
    assert list(c.paginate("/things", page_size=2)) == [1, 2, 3]
    assert len(sess.calls) == 2


def test_paginate_respects_server_capped_limit():
    # asked for 1000, server answers 2 per page: a "short" page vs. our request must not stop early
    c, sess = make(page([1, 2], limit=2), page([3, 4], limit=2), page([], limit=2))
    assert list(c.paginate("/things", page_size=1000)) == [1, 2, 3, 4]


def test_paginate_empty():
    c, _ = make(page([], total=0))
    assert list(c.paginate("/things")) == []


def test_ping_reports_counts_only():
    from collibra_toolkit.health import ping

    items = [{"id": f"id{i}", "name": "SECRET"} for i in range(5)]
    first = FakeResp(payload={"results": items[:2], "total": 5, "limit": 2, "offset": 0})
    pages = [FakeResp(payload={"results": items[i:i + 2], "total": 5, "limit": 2}) for i in (0, 2, 4)]
    c, _ = make(first, *pages)
    out = ping(c)
    assert "total communities: 5" in out[2] and "got 5, unique ids 5" in out[3]
    assert "SECRET" not in "\n".join(out)


def test_toolkit_cli_ping_and_error_messages(monkeypatch, capsys):
    from collibra_toolkit.cli import main

    items = [{"id": f"id{i}"} for i in range(5)]
    pages = [FakeResp(payload={"results": items[i:i + 2], "total": 5, "limit": 2}) for i in (0, 0, 2, 4)]
    client, _ = make(*pages)
    monkeypatch.setattr(CollibraClient, "from_env", classmethod(lambda cls, *a, **k: client))
    main(["ping"])
    assert "reachable: yes" in capsys.readouterr().out

    denied, _ = make(FakeResp(401, b"nope"))
    monkeypatch.setattr(CollibraClient, "from_env", classmethod(lambda cls, *a, **k: denied))
    with pytest.raises(SystemExit) as info:
        main(["ping"])
    assert "HTTP 401" in str(info.value) and "COLLIBRA_USER" in str(info.value)


def test_toolkit_cli_delegates_to_initiatives(tmp_path, capsys):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from collibra_toolkit.cli import main

    d = tmp_path / "asset"
    d.mkdir()
    pq.write_table(pa.table({"id": [1, 2]}), d / "p.parquet")
    main(["insights", "query", str(tmp_path), "select count(*) as n from asset"])
    assert capsys.readouterr().out.splitlines() == ["n", "2"]


# ------------------------------------------------------------------ OAuth (client credentials)

from fakes import RoutedSession  # noqa: E402

TOKEN = ("POST", "/rest/oauth/v2/token")
ITEMS = ("GET", "/rest/2.0/communities")


def token_resp(token="tok1", expires=3600):
    return FakeResp(200, payload={"access_token": token, "expires_in": expires})


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def oauth(routes, clock=None):
    sess = RoutedSession(routes)
    client = CollibraClient("https://x.collibra.com", client_id="app-id", client_secret="s3cret",
                            session=sess, clock=clock or Clock(), sleep=lambda s: None)
    return client, sess


def test_oauth_fetches_one_token_and_reuses_it():
    c, sess = oauth({TOKEN: [token_resp()], ITEMS: [FakeResp(200, payload={})]})
    c.get_json("/communities")
    c.get_json("/communities")
    token_calls = [x for x in sess.calls if x[0] == "POST"]
    assert len(token_calls) == 1
    assert token_calls[0][2]["data"] == {"grant_type": "client_credentials", "client_id": "app-id", "client_secret": "s3cret"}
    gets = [x for x in sess.calls if x[0] == "GET"]
    assert all(g[2]["headers"]["Authorization"] == "Bearer tok1" for g in gets)
    assert all("s3cret" not in repr(g) for g in gets)           # the secret only ever goes to the token endpoint


def test_oauth_refreshes_before_expiry():
    clock = Clock()
    c, sess = oauth({TOKEN: [token_resp("tok1", 3600), token_resp("tok2", 3600)], ITEMS: [FakeResp(200, payload={})]}, clock)
    c.get_json("/communities")
    clock.now = 3539                                             # still before 3600 s minus the 60 s margin
    c.get_json("/communities")
    assert [x[2]["headers"]["Authorization"] for x in sess.calls if x[0] == "GET"] == ["Bearer tok1", "Bearer tok1"]
    clock.now = 3540
    c.get_json("/communities")
    assert sess.calls[-1][2]["headers"]["Authorization"] == "Bearer tok2"


def test_oauth_replaces_a_revoked_token_once():
    c, sess = oauth({TOKEN: [token_resp("old"), token_resp("new")],
                     ITEMS: [FakeResp(401, b"expired"), FakeResp(200, payload={"ok": 1})]})
    assert c.get_json("/communities") == {"ok": 1}
    assert [x[0] for x in sess.calls] == ["POST", "GET", "POST", "GET"]
    assert sess.calls[-1][2]["headers"]["Authorization"] == "Bearer new"


def test_oauth_gives_up_after_one_retry():
    c, sess = oauth({TOKEN: [token_resp("a"), token_resp("b")], ITEMS: [FakeResp(401, b"nope")]})
    with pytest.raises(CollibraAuthError):
        c.get_json("/communities")
    assert [x[0] for x in sess.calls].count("GET") == 2


def test_oauth_token_errors_are_typed_and_never_contain_the_secret():
    c, _ = oauth({TOKEN: [FakeResp(401, b"invalid_client")]})
    with pytest.raises(CollibraAuthError) as info:
        c.get_json("/communities")
    assert "OAuth token request rejected" in str(info.value) and "s3cret" not in str(info.value)

    c, _ = oauth({TOKEN: [FakeResp(200, payload={"error": "weird"})]})
    with pytest.raises(CollibraError, match="access_token"):
        c.get_json("/communities")

    boom = CollibraClient("https://x", client_id="i", client_secret="s3cret",
                          session=FakeSession(FakeResp(), raises=requests.ConnectionError("s3cret in message")), sleep=lambda s: None)
    with pytest.raises(CollibraError) as info:
        boom.get_json("/communities")
    assert "s3cret" not in str(info.value)


def test_oauth_from_env_and_precedence():
    env = {"COLLIBRA_URL": "https://x", "COLLIBRA_CLIENT_ID": "i", "COLLIBRA_CLIENT_SECRET": "s",
           "COLLIBRA_TOKEN": "static", "COLLIBRA_USER": "u", "COLLIBRA_PASSWORD": "p"}
    sess = FakeSession(FakeResp())
    c = CollibraClient.from_env(env, session=sess)
    assert c._oauth == ("i", "s") and sess.auth is None and "Authorization" not in sess.headers
    # a lone id without a secret is not enough, so it falls through to the next method
    env2 = {"COLLIBRA_URL": "https://x", "COLLIBRA_CLIENT_ID": "i", "COLLIBRA_TOKEN": "static"}
    sess2 = FakeSession(FakeResp())
    CollibraClient.from_env(env2, session=sess2)
    assert sess2.headers["Authorization"] == "Bearer static"


# ------------------------------------------------------------------ retries: 429 and 5xx

from collibra_toolkit import CollibraRateLimitError, CollibraServerError  # noqa: E402
from collibra_toolkit.client import parse_retry_after  # noqa: E402


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


def test_oauth_refresh_and_retries_work_together():
    sess = RoutedSession({TOKEN: [token_resp("a"), token_resp("b")],
                          ITEMS: [FakeResp(401, b"expired"), FakeResp(429, b"", headers={"Retry-After": "1"}), FakeResp(200, payload={"ok": 1})]})
    slept = []
    c = CollibraClient("https://x.collibra.com", client_id="i", client_secret="s", session=sess, clock=Clock(), sleep=slept.append)
    assert c.get_json("/communities") == {"ok": 1} and slept == [1.0]


def test_parse_retry_after_formats():
    assert parse_retry_after("5") == 5.0
    assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0    # a date in the past means: retry now
    assert parse_retry_after("garbage") is None and parse_retry_after(None) is None


def test_auth_method_reports_the_credentials_really_used():
    s = FakeSession(FakeResp())
    assert CollibraClient("https://x", client_id="i", client_secret="s", session=s).auth_method == "oauth"
    assert CollibraClient("https://x", token="t", session=FakeSession(FakeResp())).auth_method == "token"
    assert CollibraClient("https://x", username="u", password="p", session=FakeSession(FakeResp())).auth_method == "basic"
    # an empty secret silently falls back: this is exactly why ping prints the method
    env = {"COLLIBRA_URL": "https://x", "COLLIBRA_CLIENT_ID": "i", "COLLIBRA_CLIENT_SECRET": "", "COLLIBRA_USER": "u", "COLLIBRA_PASSWORD": "p"}
    assert CollibraClient.from_env(env, session=FakeSession(FakeResp())).auth_method == "basic"

"""Authentication methods: basic, token, OAuth client credentials."""

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
    assert c.auth_method == "oauth" and sess.auth is None and "Authorization" not in sess.headers
    # a lone id without a secret is not enough, so it falls through to the next method
    env2 = {"COLLIBRA_URL": "https://x", "COLLIBRA_CLIENT_ID": "i", "COLLIBRA_TOKEN": "static"}
    sess2 = FakeSession(FakeResp())
    CollibraClient.from_env(env2, session=sess2)
    assert sess2.headers["Authorization"] == "Bearer static"


def test_oauth_refresh_and_retries_work_together():
    sess = RoutedSession({TOKEN: [token_resp("a"), token_resp("b")],
                          ITEMS: [FakeResp(401, b"expired"), FakeResp(429, b"", headers={"Retry-After": "1"}), FakeResp(200, payload={"ok": 1})]})
    slept = []
    c = CollibraClient("https://x.collibra.com", client_id="i", client_secret="s", session=sess, clock=Clock(), sleep=slept.append)
    assert c.get_json("/communities") == {"ok": 1} and slept == [1.0]


def test_auth_method_reports_the_credentials_really_used():
    s = FakeSession(FakeResp())
    assert CollibraClient("https://x", client_id="i", client_secret="s", session=s).auth_method == "oauth"
    assert CollibraClient("https://x", token="t", session=FakeSession(FakeResp())).auth_method == "token"
    assert CollibraClient("https://x", username="u", password="p", session=FakeSession(FakeResp())).auth_method == "basic"
    # an empty secret silently falls back: this is exactly why ping prints the method
    env = {"COLLIBRA_URL": "https://x", "COLLIBRA_CLIENT_ID": "i", "COLLIBRA_CLIENT_SECRET": "", "COLLIBRA_USER": "u", "COLLIBRA_PASSWORD": "p"}
    assert CollibraClient.from_env(env, session=FakeSession(FakeResp())).auth_method == "basic"

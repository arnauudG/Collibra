"""Authentication methods. Each is an ``Authenticator``; the client only knows that interface."""

from __future__ import annotations

import time
from collections.abc import Callable

import requests

from .errors import CollibraAuthError, CollibraError

TOKEN_PATH = "/rest/oauth/v2/token"  # OAuth token endpoint (not under /rest/2.0)
TOKEN_REFRESH_MARGIN = 60  # seconds before expiry at which a cached token is replaced


class Authenticator:
    """Base class: ``bind`` once to a session, then ``headers`` per request."""

    name = "none"
    refreshable = False  # True when a 401 can be cured by fetching new credentials

    def bind(self, session: requests.Session, base_url: str, timeout: float) -> None:
        pass

    def headers(self, force_refresh: bool = False) -> dict[str, str]:
        return {}


class BasicAuth(Authenticator):
    name = "basic"

    def __init__(self, username: str, password: str):
        self._credentials = (username, password)

    def bind(self, session, base_url, timeout):
        session.auth = self._credentials


class BearerToken(Authenticator):
    """A static token: never refreshed."""

    name = "token"

    def __init__(self, token: str):
        self._token = token

    def bind(self, session, base_url, timeout):
        session.headers["Authorization"] = f"Bearer {self._token}"


class OAuthClientCredentials(Authenticator):
    """OAuth 2.0 client-credentials grant for an *integration* application.

    The access token is cached, replaced ``TOKEN_REFRESH_MARGIN`` seconds before it expires and on
    demand. The secret travels only in the POST body to the token endpoint.
    """

    name = "oauth"
    refreshable = True

    def __init__(self, client_id: str, client_secret: str, clock: Callable[[], float] = time.monotonic):
        self._id, self._secret, self._clock = client_id, client_secret, clock
        self._access_token: str | None = None
        self._expires_at = 0.0

    def bind(self, session, base_url, timeout):
        self._session, self._base_url, self._timeout = session, base_url, timeout

    def _fetch(self) -> str:
        try:
            resp = self._session.request(
                "POST",
                self._base_url + TOKEN_PATH,
                data={"grant_type": "client_credentials", "client_id": self._id, "client_secret": self._secret},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise CollibraError(f"token request failed: {type(exc).__name__}") from exc
        if resp.status_code >= 400:
            raise CollibraAuthError(resp.status_code, f"OAuth token request rejected: {(resp.text or '')[:200]}")
        try:
            payload = resp.json()
            token = payload["access_token"]
        except (ValueError, KeyError, TypeError):
            raise CollibraError("OAuth token response did not contain an access_token") from None
        lifetime = payload.get("expires_in")
        lifetime = int(lifetime) if isinstance(lifetime, (int, float, str)) and str(lifetime).isdigit() else 3600
        self._access_token = token
        self._expires_at = self._clock() + max(lifetime - TOKEN_REFRESH_MARGIN, 0)
        return token

    def headers(self, force_refresh: bool = False) -> dict[str, str]:
        if force_refresh or not self._access_token or self._clock() >= self._expires_at:
            self._fetch()
        return {"Authorization": f"Bearer {self._access_token}"}


def select_authenticator(
    username: str | None = None,
    password: str | None = None,
    token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Authenticator:
    """Precedence: OAuth client credentials, then a static token, then basic. Incomplete pairs are skipped."""
    if client_id and client_secret:
        return OAuthClientCredentials(client_id, client_secret, clock)
    if token:
        return BearerToken(token)
    if username and password:
        return BasicAuth(username, password)
    raise CollibraError("provide client_id+client_secret (OAuth), a token, or username+password")

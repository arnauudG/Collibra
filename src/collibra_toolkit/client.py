"""Generic Collibra REST client: authentication, requests, errors, pagination.

Knows nothing about Insights. Domain-specific clients (see ``insights.py``) take a
``CollibraClient`` and compose on top of it.
"""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable, Iterator, Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

API_ROOT = "/rest/2.0"
TOKEN_PATH = "/rest/oauth/v2/token"  # OAuth token endpoint (not under /rest/2.0)
_TOKEN_REFRESH_MARGIN = 60  # seconds before expiry at which a cached token is replaced
_IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}  # safe to repeat after a 5xx or a lost connection
_RETRY_STATUS = {429, 500, 502, 503, 504}


class CollibraError(Exception):
    pass


class CollibraHTTPError(CollibraError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


class CollibraAuthError(CollibraHTTPError):
    """401 / 403: bad credentials or missing permission or licence."""


class CollibraNotFound(CollibraHTTPError):
    """404."""


class CollibraRateLimitError(CollibraHTTPError):
    """429 that persisted after all retries. ``retry_after`` is the server's hint in seconds, if any."""

    def __init__(self, status_code: int, message: str, retry_after: float | None = None):
        super().__init__(status_code, message)
        self.retry_after = retry_after


class CollibraServerError(CollibraHTTPError):
    """5xx that persisted after all retries."""


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    """``Retry-After`` is either a number of seconds or an HTTP date. Returns seconds (>= 0) or None."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max((when - (now or datetime.now(timezone.utc))).total_seconds(), 0.0)


def _http_error(resp: requests.Response) -> CollibraHTTPError:
    message = (resp.text or "")[:200]
    if resp.status_code == 429:
        return CollibraRateLimitError(429, message, parse_retry_after((getattr(resp, "headers", None) or {}).get("Retry-After")))
    if resp.status_code >= 500:
        return CollibraServerError(resp.status_code, message)
    cls = {401: CollibraAuthError, 403: CollibraAuthError, 404: CollibraNotFound}.get(resp.status_code, CollibraHTTPError)
    return cls(resp.status_code, message)


class CollibraClient:
    """Authenticated client for the Collibra REST API v2.

    Authentication, in order of precedence: OAuth 2.0 client credentials (``client_id`` +
    ``client_secret``, a registered *integration* OAuth application; tokens are fetched,
    cached and refreshed automatically), a static bearer ``token``, or basic ``username`` +
    ``password``.
    """

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 60,
        client_id: str | None = None,
        client_secret: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        retries: int = 4,
        backoff: float = 0.5,
        max_wait: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[float], float] = lambda delay: random.uniform(delay / 2, delay),
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self._clock = clock
        self.retries, self.backoff, self.max_wait = retries, backoff, max_wait
        self._sleep, self._jitter = sleep, jitter
        self._oauth: tuple[str, str] | None = None
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        if client_id and client_secret:
            self._oauth = (client_id, client_secret)
        elif token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            self.session.auth = (username, password)
        else:
            raise CollibraError("provide client_id+client_secret (OAuth), a token, or username+password")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None, **kwargs: Any) -> CollibraClient:
        """Build from COLLIBRA_URL plus COLLIBRA_CLIENT_ID/COLLIBRA_CLIENT_SECRET (OAuth),
        COLLIBRA_TOKEN, or COLLIBRA_USER/COLLIBRA_PASSWORD."""
        env = os.environ if environ is None else environ
        if "COLLIBRA_URL" not in env:
            raise CollibraError("COLLIBRA_URL is not set")
        return cls(
            env["COLLIBRA_URL"],
            username=env.get("COLLIBRA_USER"),
            password=env.get("COLLIBRA_PASSWORD"),
            token=env.get("COLLIBRA_TOKEN"),
            client_id=env.get("COLLIBRA_CLIENT_ID"),
            client_secret=env.get("COLLIBRA_CLIENT_SECRET"),
            **kwargs,
        )

    @property
    def auth_method(self) -> str:
        """Which credentials this client really uses: ``oauth``, ``token`` or ``basic``."""
        return "oauth" if self._oauth else "token" if "Authorization" in self.session.headers else "basic"

    # ------------------------------------------------------------------ OAuth

    def _fetch_token(self) -> str:
        """Client-credentials grant; the secret travels only in the POST body."""
        assert self._oauth is not None
        client_id, client_secret = self._oauth
        try:
            resp = self.session.request(
                "POST",
                self.base_url + TOKEN_PATH,
                data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
                timeout=self.timeout,
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
        self._token_expires_at = self._clock() + max(lifetime - _TOKEN_REFRESH_MARGIN, 0)
        return token

    def _bearer(self, force_refresh: bool = False) -> str:
        if force_refresh or not self._access_token or self._clock() >= self._token_expires_at:
            return self._fetch_token()
        return self._access_token

    def url(self, path: str) -> str:
        """``path`` is relative to /rest/2.0 (e.g. ``/communities``)."""
        return f"{self.base_url}{API_ROOT}/{path.lstrip('/')}"

    def _wait(self, attempt: int, retry_after: float | None) -> None:
        """Sleep before retry number ``attempt`` (0-based): the server's hint, else exponential backoff."""
        delay = retry_after if retry_after is not None else self._jitter(min(self.max_wait, self.backoff * 2**attempt))
        self._sleep(min(delay, self.max_wait))

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send a request; map failures to ``CollibraError`` subclasses. Redirects are followed.

        * OAuth: an expired or revoked token is replaced once before giving up on a 401.
        * 429 is retried for every method (the request was not processed); 500/502/503/504 and
          lost connections only for methods that are safe to repeat. Backoff is exponential
          with jitter, ``Retry-After`` is honoured, waits are capped at ``max_wait``.
        """
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("allow_redirects", True)
        safe = method.upper() in _IDEMPOTENT
        attempt, force_token, refreshed = 0, False, False
        while True:
            call_kwargs = dict(kwargs)
            if self._oauth:
                headers = dict(call_kwargs.get("headers") or {})
                headers["Authorization"] = f"Bearer {self._bearer(force_refresh=force_token)}"
                call_kwargs["headers"] = headers
                force_token = False
            try:
                resp = self.session.request(method, self.url(path), **call_kwargs)
            except requests.RequestException as exc:
                transient = isinstance(exc, (requests.ConnectionError, requests.Timeout)) and not isinstance(exc, requests.exceptions.SSLError)
                if safe and transient and attempt < self.retries:
                    self._wait(attempt, None)
                    attempt += 1
                    continue
                # class name only: the message can embed a pre-signed URL
                raise CollibraError(f"request failed: {type(exc).__name__}") from exc
            if resp.status_code == 401 and self._oauth and not refreshed:
                refreshed, force_token = True, True
                resp.close()
                continue
            retryable = resp.status_code == 429 or (resp.status_code in _RETRY_STATUS and safe)
            if retryable and attempt < self.retries:
                hint = parse_retry_after((getattr(resp, "headers", None) or {}).get("Retry-After"))
                resp.close()
                self._wait(attempt, hint)
                attempt += 1
                continue
            if resp.status_code >= 400:
                raise _http_error(resp)
            return resp

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params).json()

    def paginate(
        self, path: str, params: Mapping[str, Any] | None = None, page_size: int = 1000
    ) -> Iterator[Any]:
        """Yield items of ``results`` across offset/limit pages.

        Assumes Collibra's usual ``{"total", "offset", "limit", "results"}`` envelope.
        Verified live on ``/communities`` (2026-10-11): envelope keys and multi-page walk as assumed.
        Other endpoints are untested.
        """
        offset = 0
        while True:
            page = self.get_json(path, {**(params or {}), "offset": offset, "limit": page_size})
            results = page.get("results", [])
            yield from results
            offset += len(results)
            limit = page.get("limit") or page_size  # the server may cap our page size
            total = page.get("total")
            if not results or (total and offset >= total) or (not total and len(results) < limit):
                return

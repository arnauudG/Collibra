"""``CollibraClient``: composes an authenticator, a retry policy and pagination around ``requests``."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import requests

from .auth import Authenticator, select_authenticator
from .errors import CollibraError, http_error
from .pagination import paginate
from .retry import RetryPolicy, _half_jitter, parse_retry_after

API_ROOT = "/rest/2.0"


class CollibraClient:
    """Authenticated client for the Collibra REST API v2.

    Pass ``auth=`` and ``retry=`` objects to compose it explicitly, or use the shortcuts
    (``client_id``/``client_secret``, ``token``, ``username``/``password``, ``retries``…), which
    build them for you. Shortcut precedence: OAuth, then token, then basic.
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
        jitter: Callable[[float], float] = _half_jitter,
        *,
        auth: Authenticator | None = None,
        retry: RetryPolicy | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.auth = auth or select_authenticator(username, password, token, client_id, client_secret, clock)
        self.retry = retry or RetryPolicy(retries, backoff, max_wait, sleep, jitter)
        self.auth.bind(self.session, self.base_url, self.timeout)

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
        return self.auth.name

    def url(self, path: str) -> str:
        """``path`` is relative to /rest/2.0 (e.g. ``/communities``)."""
        return f"{self.base_url}{API_ROOT}/{path.lstrip('/')}"

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send a request; map failures to ``CollibraError`` subclasses. Redirects are followed.

        * An authenticator that can refresh (OAuth) gets one new credential on a 401.
        * Retries follow ``self.retry``: 429 for every method, 5xx and lost connections only for
          methods safe to repeat, ``Retry-After`` honoured, waits capped.
        """
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("allow_redirects", True)
        attempt, force_refresh, refreshed = 0, False, False
        while True:
            call_kwargs = dict(kwargs)
            extra = self.auth.headers(force_refresh=force_refresh)
            force_refresh = False
            if extra:
                call_kwargs["headers"] = {**(call_kwargs.get("headers") or {}), **extra}
            try:
                resp = self.session.request(method, self.url(path), **call_kwargs)
            except requests.RequestException as exc:
                if self.retry.retries_error(method, exc) and attempt < self.retry.retries:
                    self.retry.wait(attempt)
                    attempt += 1
                    continue
                # class name only: the message can embed a pre-signed URL
                raise CollibraError(f"request failed: {type(exc).__name__}") from exc
            if resp.status_code == 401 and self.auth.refreshable and not refreshed:
                refreshed, force_refresh = True, True
                resp.close()
                continue
            if self.retry.retries_status(method, resp.status_code) and attempt < self.retry.retries:
                hint = parse_retry_after((getattr(resp, "headers", None) or {}).get("Retry-After"))
                resp.close()
                self.retry.wait(attempt, hint)
                attempt += 1
                continue
            if resp.status_code >= 400:
                raise http_error(resp)
            return resp

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params).json()

    def paginate(self, path: str, params: Mapping[str, Any] | None = None, page_size: int = 1000) -> Iterator[Any]:
        return paginate(self.get_json, path, params, page_size)

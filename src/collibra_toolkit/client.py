"""Generic Collibra REST client: authentication, requests, errors, pagination.

Knows nothing about Insights. Domain-specific clients (see ``insights.py``) take a
``CollibraClient`` and compose on top of it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from typing import Any

import requests

API_ROOT = "/rest/2.0"


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


def _http_error(resp: requests.Response) -> CollibraHTTPError:
    cls = {401: CollibraAuthError, 403: CollibraAuthError, 404: CollibraNotFound}.get(
        resp.status_code, CollibraHTTPError
    )
    return cls(resp.status_code, (resp.text or "")[:200])


class CollibraClient:
    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            self.session.auth = (username, password)
        else:
            raise CollibraError("provide username+password or token")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None, **kwargs: Any) -> CollibraClient:
        """Build from COLLIBRA_URL plus COLLIBRA_USER/COLLIBRA_PASSWORD or COLLIBRA_TOKEN."""
        env = os.environ if environ is None else environ
        if "COLLIBRA_URL" not in env:
            raise CollibraError("COLLIBRA_URL is not set")
        return cls(
            env["COLLIBRA_URL"],
            username=env.get("COLLIBRA_USER"),
            password=env.get("COLLIBRA_PASSWORD"),
            token=env.get("COLLIBRA_TOKEN"),
            **kwargs,
        )

    def url(self, path: str) -> str:
        """``path`` is relative to /rest/2.0 (e.g. ``/communities``)."""
        return f"{self.base_url}{API_ROOT}/{path.lstrip('/')}"

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        """Send a request; map failures to ``CollibraError`` subclasses. Redirects are followed."""
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("allow_redirects", True)
        try:
            resp = self.session.request(method, self.url(path), **kwargs)
        except requests.RequestException as exc:
            # class name only: the message can embed a pre-signed URL
            raise CollibraError(f"request failed: {type(exc).__name__}") from exc
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

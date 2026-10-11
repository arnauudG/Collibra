"""Typed errors raised by the client. Callers can react to the class instead of parsing messages."""

from __future__ import annotations

import requests

from .retry import parse_retry_after


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


def http_error(resp: requests.Response) -> CollibraHTTPError:
    """Map a failed response to the most specific error class."""
    message = (resp.text or "")[:200]
    if resp.status_code == 429:
        hint = parse_retry_after((getattr(resp, "headers", None) or {}).get("Retry-After"))
        return CollibraRateLimitError(429, message, hint)
    if resp.status_code >= 500:
        return CollibraServerError(resp.status_code, message)
    cls = {401: CollibraAuthError, 403: CollibraAuthError, 404: CollibraNotFound}.get(resp.status_code, CollibraHTTPError)
    return cls(resp.status_code, message)

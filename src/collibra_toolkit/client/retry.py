"""Retry policy: which failures are repeated, how long to wait. Knows nothing about HTTP clients."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})  # safe to repeat after a 5xx or lost connection
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


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


def _half_jitter(delay: float) -> float:
    return random.uniform(delay / 2, delay)


@dataclass
class RetryPolicy:
    """429 is retried for every method (the request was not processed); 5xx and lost connections
    only for methods that are safe to repeat. Exponential backoff with jitter; every wait is capped."""

    retries: int = 4
    backoff: float = 0.5
    max_wait: float = 60.0
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)
    jitter: Callable[[float], float] = field(default=_half_jitter, repr=False)

    def retries_status(self, method: str, status: int) -> bool:
        return status == 429 or (status in RETRY_STATUSES and method.upper() in IDEMPOTENT_METHODS)

    def retries_error(self, method: str, exc: Exception) -> bool:
        """Lost connections and timeouts, never SSL errors (permanent), only for repeatable methods."""
        transient = isinstance(exc, (requests.ConnectionError, requests.Timeout)) and not isinstance(
            exc, requests.exceptions.SSLError
        )
        return transient and method.upper() in IDEMPOTENT_METHODS

    def wait(self, attempt: int, retry_after: float | None = None) -> None:
        """Sleep before retry number ``attempt`` (0-based): the server's hint, else exponential backoff."""
        delay = retry_after if retry_after is not None else self.jitter(min(self.max_wait, self.backoff * 2**attempt))
        self.sleep(min(delay, self.max_wait))

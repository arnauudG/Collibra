"""Reusable Collibra tooling.

``collibra_toolkit`` itself is the generic layer (authenticated REST client, typed errors,
pagination). Each initiative lives in its own subpackage and composes the client, for
example ``collibra_toolkit.insights``.
"""

from .client import (
    CollibraAuthError,
    CollibraClient,
    CollibraError,
    CollibraHTTPError,
    CollibraNotFound,
    CollibraRateLimitError,
    CollibraServerError,
)

__all__ = [
    "CollibraClient", "CollibraError", "CollibraHTTPError", "CollibraAuthError", "CollibraNotFound",
    "CollibraRateLimitError", "CollibraServerError",
]

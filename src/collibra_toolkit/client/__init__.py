"""The generic Collibra REST client. Knows nothing about any initiative built on top of it.

Layers (each imports only the ones above it in this list):
``retry`` -> ``errors`` -> ``auth`` -> ``pagination`` -> ``core`` (CollibraClient) -> ``health``.
"""

from .auth import Authenticator, BasicAuth, BearerToken, OAuthClientCredentials
from .core import CollibraClient
from .errors import (
    CollibraAuthError,
    CollibraError,
    CollibraHTTPError,
    CollibraNotFound,
    CollibraRateLimitError,
    CollibraServerError,
)
from .retry import RetryPolicy

__all__ = [
    "CollibraClient", "RetryPolicy",
    "Authenticator", "BasicAuth", "BearerToken", "OAuthClientCredentials",
    "CollibraError", "CollibraHTTPError", "CollibraAuthError", "CollibraNotFound",
    "CollibraRateLimitError", "CollibraServerError",
]

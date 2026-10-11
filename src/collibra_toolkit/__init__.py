"""Reusable Collibra tooling.

``collibra_toolkit.client`` is the generic layer (authenticated REST client, typed errors,
retries, pagination). Each initiative lives in its own subpackage and composes the client, for
example ``collibra_toolkit.insights``. Names are exported lazily, so importing a sub-package
does not import the others.
"""

from ._lazy import lazy_exports

_EXPORTS = {name: ".client" for name in (
    "CollibraClient", "CollibraError", "CollibraHTTPError", "CollibraAuthError", "CollibraNotFound",
    "CollibraRateLimitError", "CollibraServerError",
)}
__all__ = list(_EXPORTS)
__getattr__, __dir__ = lazy_exports(__name__, _EXPORTS)

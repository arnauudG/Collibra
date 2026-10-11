"""Evidence about an export: ``offline`` needs only a Snapshot, ``live`` also needs the REST client.

Exports are lazy so the offline layer works without ``requests``.
"""

from ..._lazy import lazy_exports

_EXPORTS = {"snapshot_report": ".offline"} | {
    name: ".live" for name in ("live_report", "lookup_id", "describe", "resolve_id", "role_resources", "probe_role")
}
__all__ = list(_EXPORTS)
__getattr__, __dir__ = lazy_exports(__name__, _EXPORTS)

"""Insights Data Access: download snapshots, explore them locally, model them for analysis.

Layers (the sub-packages): ``tables`` (documented tables), ``api`` (download; needs the generic
client), ``store`` (local DuckDB snapshot; no network), ``model`` (star schema), ``diagnostics``
(offline and live evidence). Public names load lazily, so ``InsightsClient`` can be used
without DuckDB and ``Snapshot`` without ``requests``.
"""

from .._lazy import lazy_exports

_EXPORTS = {
    "InsightsClient": ".api",
    "ENDPOINTS": ".api",
    "Snapshot": ".store",
    "build_model": ".model",
    "check_model": ".model",
    "CORE_TABLES": ".tables",
    "OPTIONAL_TABLES": ".tables",
    "DOCUMENTED_TABLES": ".tables",
}
__all__ = list(_EXPORTS)
__getattr__, __dir__ = lazy_exports(__name__, _EXPORTS)

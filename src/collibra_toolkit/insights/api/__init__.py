"""Downloading snapshots from Collibra. Needs the generic client, not DuckDB."""

from .download import ENDPOINTS, InsightsClient
from .retention import retention_note, validate_snapshot_date

__all__ = ["InsightsClient", "ENDPOINTS", "retention_note", "validate_snapshot_date"]

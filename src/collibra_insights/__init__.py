"""Composable Collibra tooling: a generic REST client, Insights snapshot download, local analysis."""

from .client import CollibraAuthError, CollibraClient, CollibraError, CollibraHTTPError, CollibraNotFound
from .explore import Snapshot
from .insights import InsightsClient
from .tables import DOCUMENTED_TABLES

__all__ = [
    "CollibraClient", "CollibraError", "CollibraHTTPError", "CollibraAuthError", "CollibraNotFound",
    "InsightsClient", "Snapshot", "DOCUMENTED_TABLES",
]

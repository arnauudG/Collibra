"""Insights Data Access: download snapshots, explore them locally, model them for analysis."""

from .client import InsightsClient
from .model import build_model, check_model
from .snapshot import Snapshot
from .tables import CORE_TABLES, DOCUMENTED_TABLES, OPTIONAL_TABLES

__all__ = [
    "InsightsClient", "Snapshot", "build_model", "check_model",
    "CORE_TABLES", "OPTIONAL_TABLES", "DOCUMENTED_TABLES",
]

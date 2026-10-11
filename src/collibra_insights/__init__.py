"""Client and local explorer for Collibra Insights Data Access snapshots."""

from .client import CollibraClient, CollibraError
from .explore import Snapshot
from .tables import DOCUMENTED_TABLES

__all__ = ["CollibraClient", "CollibraError", "Snapshot", "DOCUMENTED_TABLES"]

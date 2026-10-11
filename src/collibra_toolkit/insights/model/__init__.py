"""Star-schema model over a Snapshot, and its conformance checks."""

from .checks import check_model
from .views import build_model

__all__ = ["build_model", "check_model"]

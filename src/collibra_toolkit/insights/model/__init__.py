"""Star-schema model over a Snapshot (silver), its conformance checks, and the gold tables on top."""

from .checks import check_model
from .gold import GoldConfig, build_gold
from .views import build_model

__all__ = ["build_model", "check_model", "build_gold", "GoldConfig"]

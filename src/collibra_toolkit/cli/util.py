"""Shared CLI plumbing: turn Collibra errors into one-line messages."""

from __future__ import annotations

import sys
from collections.abc import Callable

from ..client import CollibraAuthError, CollibraError


def run(fn: Callable[[list[str] | None], None], argv: list[str] | None = None) -> None:
    try:
        fn(argv)
    except CollibraAuthError as exc:
        sys.exit(
            f"error: {exc}\nCheck COLLIBRA_CLIENT_ID/COLLIBRA_CLIENT_SECRET (or COLLIBRA_USER/COLLIBRA_PASSWORD, "
            "COLLIBRA_TOKEN), and that the account may use the API."
        )
    except CollibraError as exc:
        sys.exit(f"error: {exc}")

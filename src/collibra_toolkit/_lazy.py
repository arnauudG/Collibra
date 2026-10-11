"""Lazy package exports (PEP 562), so importing one layer never imports another.

Used by package ``__init__`` files whose public names live in sub-modules with heavier
dependencies (for example DuckDB or ``requests``). Imports nothing first-party.
"""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Any, Callable


def lazy_exports(package: str, mapping: dict[str, str]) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """Return ``(__getattr__, __dir__)`` serving ``mapping`` (name -> relative module) on demand."""

    def __getattr__(name: str) -> Any:
        if name not in mapping:
            raise AttributeError(f"module {package!r} has no attribute {name!r}")
        value = getattr(import_module(mapping[name], package), name)
        sys.modules[package].__dict__[name] = value
        return value

    def __dir__() -> list[str]:
        return sorted([*sys.modules[package].__dict__, *mapping])

    return __getattr__, __dir__

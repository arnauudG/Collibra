"""``collibra-toolkit``: generic commands, plus every installed initiative as a sub-command.

Initiatives are *discovered*, not imported by name: a package registers itself under the
``collibra_toolkit.initiatives`` entry-point group (in its ``pyproject.toml``), and this module
never needs editing to gain a new one.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from importlib.metadata import entry_points

from ..client import CollibraClient
from ..client.health import ping
from .util import run

INITIATIVES_GROUP = "collibra_toolkit.initiatives"

Main = Callable[[list[str] | None], None]


def initiatives() -> dict[str, Callable[[], Main]]:
    """Installed initiatives: name -> loader returning that initiative's ``main(argv)``."""
    return {ep.name: ep.load for ep in entry_points(group=INITIATIVES_GROUP)}


def _main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    registry = initiatives()
    if argv and argv[0] in registry:
        return registry[argv[0]]()(argv[1:])
    p = argparse.ArgumentParser(
        prog="collibra-toolkit", epilog="initiatives: " + (", ".join(sorted(registry)) or "(none installed)")
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping", help="check credentials and pagination against COLLIBRA_URL")
    for name in sorted(registry):
        sub.add_parser(name, help=f"the {name} initiative (run: collibra-toolkit {name} -h)")
    p.parse_args(argv)
    print("\n".join(ping(CollibraClient.from_env())))


def main(argv: list[str] | None = None) -> None:
    run(_main, argv)

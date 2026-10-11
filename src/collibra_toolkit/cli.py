"""``collibra-toolkit``: generic commands plus one sub-command per initiative."""

from __future__ import annotations

import argparse
import sys

from .cli_util import run
from .client import CollibraClient
from .health import ping


def _main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["insights"]:
        from .insights.cli import _main as insights_main

        return insights_main(argv[1:])
    p = argparse.ArgumentParser(prog="collibra-toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping", help="check credentials and pagination against COLLIBRA_URL")
    sub.add_parser("insights", help="Insights Data Access tools (run: collibra-toolkit insights -h)")
    p.parse_args(argv)
    print("\n".join(ping(CollibraClient.from_env())))


def main(argv: list[str] | None = None) -> None:
    run(_main, argv)

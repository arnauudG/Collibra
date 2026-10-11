"""``collibra-insights`` (also ``collibra-toolkit insights``): the composition root of the initiative.

Each command imports only the layers it needs, so ``download`` and ``tables-available`` work
without DuckDB. Credentials come from environment variables, never from arguments.
"""

from __future__ import annotations

import argparse
import sys

from ..cli.util import run
from ..client import CollibraClient, CollibraError
from ..client.health import ping
from .api import ENDPOINTS, InsightsClient
from .tables import DOCUMENTED_TABLES


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="collibra-insights")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download", help="download + extract a snapshot")
    d.add_argument("date", help="YYYY-MM-DD (last 31 days, a month-end, or a year-end)")
    d.add_argument("--dest", default="snapshots")
    d.add_argument("--endpoint", choices=sorted(ENDPOINTS), default="direct")

    t = sub.add_parser("tables-available", help="list the tables each snapshot ZIP contains (downloads, does not extract)")
    t.add_argument("dates", nargs="+")
    t.add_argument("--endpoint", choices=[*sorted(ENDPOINTS), "both"], default="direct")

    e = sub.add_parser("explore", help="print tables/columns of an extracted snapshot (or a folder of snapshots)")
    e.add_argument("path")

    q = sub.add_parser("query", help="run a SQL query against an extracted snapshot")
    q.add_argument("path")
    q.add_argument("sql", nargs="?", help="SQL text (or use --file)")
    q.add_argument("--file", help="read the SQL from a file instead ('-' = stdin)")
    q.add_argument("--model", action="store_true", help="also create the dim_/fact_ views first")

    k = sub.add_parser("check", help="build the model and report conformance violations")
    k.add_argument("path")

    i = sub.add_parser("investigate", help="aggregate evidence about what an export contains")
    i.add_argument("path")
    i.add_argument("--live", action="store_true", help="also compare with the REST API (needs credentials)")

    sub.add_parser("ping", help="check credentials and pagination against COLLIBRA_URL")
    return p


def _store():
    """The local-analysis layer needs DuckDB, an optional extra."""
    try:
        from .store import Snapshot
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise CollibraError("this command needs DuckDB: pip install 'collibra-toolkit[insights]'") from exc
    return Snapshot


def _tables_available(args) -> None:
    client = InsightsClient.from_env()
    endpoints = sorted(ENDPOINTS) if args.endpoint == "both" else [args.endpoint]
    for ep in endpoints:
        for day in args.dates:
            try:
                tables = client.list_tables(day, ep)
            except CollibraError as exc:
                print(f"{day} [{ep}]: {exc}")
                continue
            absent = [t for t in DOCUMENTED_TABLES if t not in tables]
            extra = [t for t in tables if t not in DOCUMENTED_TABLES]
            print(f"{day} [{ep}]: {len(tables)} tables {tables}; documented but absent: {absent or '-'}; undocumented: {extra or '-'}")


def _query(args) -> None:
    snap = _store()(args.path)
    if args.model:
        from .model import build_model

        build_model(snap)
    sql = (sys.stdin.read() if args.file == "-" else open(args.file).read()) if args.file else args.sql
    if not sql:
        raise CollibraError("give SQL text or --file")
    cur = snap.sql(sql)
    print(" | ".join(c[0] for c in cur.description))
    for row in cur.fetchall():
        print(" | ".join("" if v is None else str(v) for v in row))


def _main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.cmd == "download":
        print(InsightsClient.from_env().download_snapshot(args.date, args.dest, args.endpoint))
    elif args.cmd == "tables-available":
        _tables_available(args)
    elif args.cmd == "ping":
        print("\n".join(ping(CollibraClient.from_env())))
    elif args.cmd == "query":
        _query(args)
    elif args.cmd == "explore":
        snap = _store()(args.path)
        print(snap.report())
        if snap.missing():
            print("\nCore tables absent:", ", ".join(snap.missing()))
        if snap.optional_absent():
            print("Optional documented tables absent:", ", ".join(snap.optional_absent()))
    elif args.cmd == "check":
        from .model import check_model

        for name, n in check_model(_store()(args.path)).items():
            print(f"{'OK  ' if n == 0 else 'WARN'} {name}: {n}")
    elif args.cmd == "investigate":
        from .diagnostics import live_report, snapshot_report

        snap = _store()(args.path)
        print(snapshot_report(snap))
        if args.live:
            print("\n" + live_report(CollibraClient.from_env(), snap))


def main(argv: list[str] | None = None) -> None:
    run(_main, argv)

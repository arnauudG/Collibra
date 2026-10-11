"""``collibra-insights download|explore``. Credentials come from env vars, never argv."""

from __future__ import annotations

import argparse

from .explore import Snapshot
from .insights import InsightsClient
from .model import build_model, check_model


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="collibra-insights")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download", help="download + extract a snapshot")
    d.add_argument("date", help="YYYY-MM-DD (last 31 days or a month-end)")
    d.add_argument("--dest", default="snapshots")
    e = sub.add_parser("explore", help="print tables/columns of an extracted snapshot")
    e.add_argument("path")
    q = sub.add_parser("query", help="run a SQL query against an extracted snapshot")
    q.add_argument("path")
    q.add_argument("sql")
    q.add_argument("--model", action="store_true", help="also create the dim_/fact_ views first")
    k = sub.add_parser("check", help="build the model and report conformance violations")
    k.add_argument("path")
    args = p.parse_args(argv)

    if args.cmd == "check":
        for name, n in check_model(Snapshot(args.path)).items():
            print(f"{'OK  ' if n == 0 else 'WARN'} {name}: {n}")
        return
    if args.cmd == "query":
        snap = Snapshot(args.path)
        if args.model:
            build_model(snap)
        cur = snap.sql(args.sql)
        cols = [c[0] for c in cur.description]
        print(" | ".join(cols))
        for row in cur.fetchall():
            print(" | ".join("" if v is None else str(v) for v in row))
        return

    if args.cmd == "download":
        client = InsightsClient.from_env()
        print(client.download_snapshot(args.date, args.dest))
    else:
        snap = Snapshot(args.path)
        print(snap.report())
        if snap.missing():
            print("\nDocumented but absent:", ", ".join(snap.missing()))

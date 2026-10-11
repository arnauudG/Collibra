"""``collibra-insights download|explore``. Credentials come from env vars, never argv."""

from __future__ import annotations

import argparse
import os

from .client import CollibraClient
from .explore import Snapshot


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
    args = p.parse_args(argv)

    if args.cmd == "query":
        cur = Snapshot(args.path).sql(args.sql)
        cols = [c[0] for c in cur.description]
        print(" | ".join(cols))
        for row in cur.fetchall():
            print(" | ".join("" if v is None else str(v) for v in row))
        return

    if args.cmd == "download":
        client = CollibraClient(
            os.environ["COLLIBRA_URL"],
            username=os.environ.get("COLLIBRA_USER"),
            password=os.environ.get("COLLIBRA_PASSWORD"),
            token=os.environ.get("COLLIBRA_TOKEN"),
        )
        print(client.download_snapshot(args.date, args.dest))
    else:
        snap = Snapshot(args.path)
        print(snap.report())
        if snap.missing():
            print("\nDocumented but absent:", ", ".join(snap.missing()))

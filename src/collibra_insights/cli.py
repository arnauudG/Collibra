"""``collibra-insights download|explore``. Credentials come from env vars, never argv."""

from __future__ import annotations

import argparse
import sys
from itertools import islice

from .client import CollibraAuthError, CollibraClient, CollibraError
from .explore import Snapshot
from .insights import InsightsClient
from .model import build_model, check_model


def ping(client: CollibraClient) -> list[str]:
    """Live connectivity + pagination check. Prints counts and key names only, no content."""
    page = client.get_json("/communities", {"limit": 2})
    items = list(islice(client.paginate("/communities", page_size=2), 5))
    ids = [i.get("id") for i in items]
    return [
        "reachable: yes",
        f"envelope keys: {sorted(page)}",
        f"total communities: {page.get('total')}",
        f"paginate(page_size=2), first 5 items: got {len(items)}, unique ids {len(set(ids))}",
    ]


def main(argv: list[str] | None = None) -> None:
    try:
        _run(argv)
    except CollibraAuthError as exc:
        sys.exit(f"error: {exc}\nCheck COLLIBRA_USER / COLLIBRA_PASSWORD (or COLLIBRA_TOKEN), and that the account may use the API.")
    except CollibraError as exc:
        sys.exit(f"error: {exc}")


def _run(argv: list[str] | None = None) -> None:
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
    sub.add_parser("ping", help="check credentials and pagination against COLLIBRA_URL")
    k = sub.add_parser("check", help="build the model and report conformance violations")
    k.add_argument("path")
    args = p.parse_args(argv)

    if args.cmd == "ping":
        print("\n".join(ping(CollibraClient.from_env())))
        return
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

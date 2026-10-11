"""Small builders shared by Insights tests."""

import datetime as dt

import pyarrow as pa
import pyarrow.parquet as pq

SNAPSHOT_DAY = dt.date(2026, 10, 10)  # the day every synthetic table below is stamped with


def make_flat_snapshot(root):
    # SYNTHETIC columns, only to exercise the code; not Collibra's real schema.
    for name in ("asset", "domain", "mystery_table"):
        d = root / name
        d.mkdir(parents=True)
        pq.write_table(pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]}), d / "part-0.parquet")


def write_table(root, table, rows):
    d = root / table / "snapshot_date_year=2026" / "snapshot_date_month=10" / "snapshot_date_day=10"
    d.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([{"snapshot_date": SNAPSHOT_DAY, **r} for r in rows]), d / "p.parquet")

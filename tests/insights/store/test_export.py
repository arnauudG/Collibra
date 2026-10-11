"""Exporting views as Hive-partitioned Parquet: readable anywhere, safe to re-run."""

import duckdb

from collibra_toolkit.insights.model import build_model


def _read(path):
    return duckdb.sql(f"SELECT * FROM read_parquet('{path}/**/*.parquet', hive_partitioning=true)")


def test_export_is_partitioned_and_round_trips(snap, lake):
    build_model(snap)
    assert snap.export(["dim_asset"], lake) == {"dim_asset": 2}
    assert (lake / "dim_asset" / "snapshot_date=2026-10-10").is_dir()
    rows = _read(lake / "dim_asset")
    assert rows.count("*").fetchone() == (2,) and "snapshot_date" in rows.columns


def test_reexport_replaces_the_partition_and_never_duplicates(snap, lake):
    build_model(snap)
    snap.export(["dim_asset"], lake)
    part = lake / "dim_asset" / "snapshot_date=2026-10-10"
    (part / "data_9.parquet").write_bytes(part.joinpath(next(part.glob("*.parquet")).name).read_bytes())  # stale leftover
    snap.export(["dim_asset"], lake)
    assert _read(lake / "dim_asset").count("*").fetchone() == (2,)
    assert not (part / "data_9.parquet").exists()


def test_other_partitions_are_left_alone(snap, lake):
    build_model(snap)
    other = lake / "dim_asset" / "snapshot_date=2020-01-01"
    other.mkdir(parents=True)
    (other / "keep.parquet").write_bytes(b"history")
    snap.export(["dim_asset"], lake)
    assert (other / "keep.parquet").read_bytes() == b"history"

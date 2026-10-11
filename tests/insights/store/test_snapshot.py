"""The local snapshot store: table discovery, partitioned layout, several snapshots."""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from collibra_toolkit.insights.store import Snapshot
from tests.insights.helpers import make_flat_snapshot


def test_snapshot_discovers_tables(tmp_path):
    make_flat_snapshot(tmp_path)
    s = Snapshot(tmp_path)
    assert s.tables == ["asset", "domain", "mystery_table"]
    assert s.undocumented() == ["mystery_table"]
    assert "community" in s.missing()
    assert s.row_counts()["asset"] == 3
    assert [c[0] for c in s.describe("asset")] == ["id", "name"]
    assert "asset" in s.report()


def test_snapshot_hive_partitioned_layout(tmp_path):
    """Real snapshots: <table>/snapshot_date_year=Y/snapshot_date_month=M/snapshot_date_day=D/file.parquet"""
    for name, n in (("asset", 3), ("responsibility", 2)):
        d = tmp_path / "wrapper" / name / "snapshot_date_year=2026" / "snapshot_date_month=10" / "snapshot_date_day=10"
        d.mkdir(parents=True)
        pq.write_table(pa.table({"id": list(range(n))}), d / "part-0.parquet")
    s = Snapshot(tmp_path)
    assert s.tables == ["asset", "responsibility"]
    assert s.row_counts() == {"asset": 3, "responsibility": 2}
    assert "snapshot_date_day" in [c[0] for c in s.describe("asset")]


def test_several_snapshots_under_one_parent_are_unioned(tmp_path):
    for day, n in (("09", 3), ("10", 2)):
        d = tmp_path / f"insights-2026-10-{day}" / "asset" / "snapshot_date_year=2026" / "snapshot_date_month=10" / f"snapshot_date_day={day}"
        d.mkdir(parents=True)
        pq.write_table(pa.table({"id": list(range(n)), "snapshot_date": [f"2026-10-{day}"] * n}), d / "p.parquet")
    s = Snapshot(tmp_path)
    assert s.tables == ["asset"] and s.row_counts() == {"asset": 5}
    assert s.sql("select count(distinct snapshot_date) from asset").fetchone() == (2,)


def test_snapshot_empty_dir_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        Snapshot(tmp_path)


def test_core_vs_optional_tables(tmp_path):
    from collibra_toolkit.insights.tables import CORE_TABLES

    for name in CORE_TABLES:
        d = tmp_path / name
        d.mkdir()
        pq.write_table(pa.table({"id": [1]}), d / "p.parquet")
    s = Snapshot(tmp_path)
    assert s.missing() == [] and s.optional_absent() == ["view_events"]
    assert s.undocumented() == []


def test_table_name_rules():
    from collibra_toolkit.insights.tables import table_name

    assert table_name(("w", "asset", "snapshot_date_year=2026", "snapshot_date_day=10")) == "asset"
    assert table_name(("w", "asset")) == "asset"          # flat layout
    assert table_name(("snapshot_date_year=2026",)) is None

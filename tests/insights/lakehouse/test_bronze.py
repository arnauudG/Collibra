"""Bronze: raw files landed unchanged, with a manifest that proves what arrived."""

import json

import pyarrow as pa
import pyarrow.parquet as pq

from collibra_toolkit.insights.lakehouse import land


def test_land_copies_raw_files_and_writes_a_manifest(snap, lake):
    manifest = land(snap.path, lake / "bronze")
    assert (lake / "bronze" / "asset" / "snapshot_date_year=2026" / "snapshot_date_month=10" / "snapshot_date_day=10" / "p.parquet").exists()
    assert manifest["rows_in_source"]["asset"] == 2 and manifest["replaced"] == []
    assert all(len(f["sha256"]) == 64 and f["bytes"] > 0 for f in manifest["files"])
    saved = list((lake / "bronze" / "_manifests").glob("*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_text())["source"] == snap.path.name


def test_landing_twice_is_idempotent_and_changes_are_reported(snap, lake):
    first = land(snap.path, lake / "bronze")
    again = land(snap.path, lake / "bronze")
    assert again["replaced"] == [] and [f["path"] for f in again["files"]] == [f["path"] for f in first["files"]]

    changed = next(snap.path.rglob("asset/**/*.parquet"))
    pq.write_table(pa.table({"asset_id": ["z"]}), changed)           # the source file changes under us
    third = land(snap.path, lake / "bronze")
    assert len(third["replaced"]) == 1 and third["replaced"][0].startswith("asset/")

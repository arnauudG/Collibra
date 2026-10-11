"""The star-schema views: deduplication, labels, privacy, optional tables."""

import datetime as dt
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from collibra_toolkit.insights.store import Snapshot
from tests.insights.helpers import write_table
from collibra_toolkit.insights.model import build_model, check_model


def test_dedupes_and_flags(snap):
    build_model(snap)
    q = lambda s: snap.sql(s).fetchall()
    assert q("select count(*) from dim_community") == [(1,)]           # repeated levels collapsed
    assert q("select depth, is_root from dim_community") == [(2, False)]
    assert q("select ancestor_community_id from bridge_community_ancestor order by ancestor_level") == [("p1",), ("c1",)]
    assert q("select count(*) from fact_relation") == [(1,)]           # mirrored pair -> one row
    assert q("select count(*) from bridge_complex_relation") == [(2,)]  # one row per participant
    assert q("select asset_id from dim_asset where is_domain_missing") == [("a2",)]
    assert q("select count(*) from dim_asset") == [(2,)]               # orphan kept, not dropped
    assert q("select community_name from dim_asset where asset_id='a1'") == [("Root",)]
    assert q("select value_as_text from fact_attribute order by attribute_id") == [("hello",), ("4.0",)]
    assert q("select is_month_end from dim_snapshot") == [(False,)]
    assert q("select asset_resolution from fact_responsibility") == [("in_export",)]


def test_pii_excluded_by_default(snap):
    build_model(snap)
    cols = [c[0] for c in snap.describe("dim_user")]
    assert "username" in cols and "user_email" not in cols and "user_firstname" not in cols
    build_model(snap, include_pii=True)
    assert "user_email" in [c[0] for c in snap.describe("dim_user")]


def test_missing_table_is_a_clear_error(tmp_path):
    write_table(tmp_path, "asset", [dict(asset_id="a")])
    with pytest.raises(ValueError, match="lacks tables"):
        build_model(Snapshot(tmp_path))


def test_view_events_become_a_fact_only_when_present(snap, tmp_path_factory):
    assert "fact_view_event" in build_model(snap)
    assert snap.sql("select count(*) from fact_view_event").fetchone() == (1,)
    # a snapshot without the optional table still builds, and has no such view
    root = tmp_path_factory.mktemp("noviews")
    for src in snap.path.iterdir():
        if src.name != "view_events":
            import shutil
            shutil.copytree(src, root / src.name)
    no_views = Snapshot(root)
    assert "fact_view_event" not in build_model(no_views)

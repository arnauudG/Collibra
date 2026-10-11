import datetime as dt

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from collibra_toolkit.insights import Snapshot
from collibra_toolkit.insights.model import build_model, check_model

D = dt.date(2026, 10, 10)
# SYNTHETIC rows using the REAL column names observed in a snapshot.


def _write(root, table, rows):
    d = root / table / "snapshot_date_year=2026" / "snapshot_date_month=10" / "snapshot_date_day=10"
    d.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([{"snapshot_date": D, **r} for r in rows]), d / "p.parquet")


@pytest.fixture
def snap(tmp_path):
    comm = dict(community_description=None, is_community_system=False, uri="u", parent_community_id="p1")
    _write(tmp_path, "community", [  # c1 repeated for two hierarchy levels
        dict(community_id="c1", community_name="Root", level=1, level_community_id="p1", level_community_name="Parent", **comm),
        dict(community_id="c1", community_name="Root", level=2, level_community_id="c1", level_community_name="Root", **comm),
    ])
    _write(tmp_path, "domain", [dict(
        domain_id="d1", domain_name="Dom", domain_description=None, domain_type_id="t", domain_type_name="Glossary",
        is_domain_system=False, community_id="c1")])
    base = dict(asset_full_name="f", asset_display_name="n", asset_type_id="at", asset_type_name="Term",
                status_id="s", status_name="Approved", articulation=1.0, ratings_average=0.0, ratings_count=0,
                is_asset_system=False, creation_date=None, edited_date=None, creator_username="jdoe", editor_username="jdoe")
    _write(tmp_path, "asset", [dict(asset_id="a1", domain_id="d1", **base), dict(asset_id="a2", domain_id="gone", **base)])
    _write(tmp_path, "asset_tag", [dict(asset_id="a1", tag_id="t1", tag_name="pii")])
    _write(tmp_path, "attribute", [
        dict(attribute_id="x1", asset_id="a1", complex_relation_id=None, attribute_type_id="ty",
             attribute_type_name="Definition", kind="STRING", expression_long="hello", numeric_value=None,
             boolean_value=None, datetime_value=None, edited_date=None),
        dict(attribute_id="x2", asset_id="a1", complex_relation_id=None, attribute_type_id="ty2",
             attribute_type_name="Score", kind="NUMERIC", expression_long=None, numeric_value=4.0,
             boolean_value=None, datetime_value=None, edited_date=None),
    ])
    rel = dict(relation_type_id="rt", asset_type_id1="at", asset_type_name1="Term", asset_type_id2="at",
               asset_type_name2="Term", is_relation_generated=False)
    _write(tmp_path, "relation", [  # one relationship, stored as two mirrored rows
        dict(relation_id="r1", direction="head -> tail", role_or_corole="role", asset_id1="a1", asset_id2="a2", **rel),
        dict(relation_id="r1", direction="tail -> head", role_or_corole="corole", asset_id1="a2", asset_id2="a1", **rel),
    ])
    _write(tmp_path, "complex_relation", [
        dict(complex_relation_id="cr1", complex_relation_type_id="ct", complex_relation_type_name="T",
             relation_type_id="rt", relation_role="source", asset_id="a1"),
        dict(complex_relation_id="cr1", complex_relation_type_id="ct", complex_relation_type_name="T",
             relation_type_id="rt", relation_role="target", asset_id="a2"),
    ])
    _write(tmp_path, "responsibility", [dict(
        role_id="ro", role_name="Owner", asset_id="a1", user_id="u1", username="jdoe", user_firstname="Jane",
        user_lastname="Doe", user_email="j@x.com", user_language="en", user_licensetype="AUTHOR",
        is_user_guest=False, is_user_api=False, is_user_activated=True, is_user_enabled=True,
        is_responsibility_system=False, group_id=None, group_name=None, creation_date=None, edited_date=None)])
    _write(tmp_path, "view_events", [dict(
        event_id="e1", user_id="u1", username="jdoe", event_time=dt.datetime(2026, 10, 10, 9, 0), session_id="s1",
        asset_id="a1", asset_full_name="f", asset_display_name="n", domain_id="d1", domain_name="Dom",
        community_id="c1", community_name="Root", diagram_id=None, diagram_name=None, dashboard_id=None,
        dashboard_name=None, view_id=None, view_name=None, page_parameters=None, page_path="/asset/a1", tab_name="Overview")])
    return Snapshot(tmp_path)


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


def test_checks_report_orphan_only(snap):
    res = check_model(snap)
    assert res["asset_missing_domain"] == 1
    assert res["relation_missing_asset"] == 0 and res["community_parent_mismatch"] == 0
    assert res["relation_ids_not_stored_twice"] == 0
    assert res["dim_asset_duplicate_keys"] == 0 and res["dim_community_duplicate_keys"] == 0


def test_missing_table_is_a_clear_error(tmp_path):
    _write(tmp_path, "asset", [dict(asset_id="a")])
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

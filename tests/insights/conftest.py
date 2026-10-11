"""Shared Insights fixtures: a synthetic snapshot with the REAL column names of an export."""

import datetime as dt

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from collibra_toolkit.insights.store import Snapshot
from tests.insights.helpers import write_table

@pytest.fixture
def snap(tmp_path):
    comm = dict(community_description=None, is_community_system=False, uri="u", parent_community_id="p1")
    write_table(tmp_path, "community", [  # c1 repeated for two hierarchy levels
        dict(community_id="c1", community_name="Root", level=1, level_community_id="p1", level_community_name="Parent", **comm),
        dict(community_id="c1", community_name="Root", level=2, level_community_id="c1", level_community_name="Root", **comm),
    ])
    write_table(tmp_path, "domain", [dict(
        domain_id="d1", domain_name="Dom", domain_description=None, domain_type_id="t", domain_type_name="Glossary",
        is_domain_system=False, community_id="c1")])
    base = dict(asset_full_name="f", asset_display_name="n", asset_type_id="at", asset_type_name="Term",
                status_id="s", status_name="Approved", articulation=1.0, ratings_average=0.0, ratings_count=0,
                is_asset_system=False, creation_date=None, edited_date=None, creator_username="jdoe", editor_username="jdoe")
    write_table(tmp_path, "asset", [dict(asset_id="a1", domain_id="d1", **base), dict(asset_id="a2", domain_id="gone", **base)])
    write_table(tmp_path, "asset_tag", [dict(asset_id="a1", tag_id="t1", tag_name="pii")])
    write_table(tmp_path, "attribute", [
        dict(attribute_id="x1", asset_id="a1", complex_relation_id=None, attribute_type_id="ty",
             attribute_type_name="Definition", kind="STRING", expression_long="hello", numeric_value=None,
             boolean_value=None, datetime_value=None, edited_date=None),
        dict(attribute_id="x2", asset_id="a1", complex_relation_id=None, attribute_type_id="ty2",
             attribute_type_name="Score", kind="NUMERIC", expression_long=None, numeric_value=4.0,
             boolean_value=None, datetime_value=None, edited_date=None),
    ])
    rel = dict(relation_type_id="rt", asset_type_id1="at", asset_type_name1="Term", asset_type_id2="at",
               asset_type_name2="Term", is_relation_generated=False)
    write_table(tmp_path, "relation", [  # one relationship, stored as two mirrored rows
        dict(relation_id="r1", direction="head -> tail", role_or_corole="role", asset_id1="a1", asset_id2="a2", **rel),
        dict(relation_id="r1", direction="tail -> head", role_or_corole="corole", asset_id1="a2", asset_id2="a1", **rel),
    ])
    write_table(tmp_path, "complex_relation", [
        dict(complex_relation_id="cr1", complex_relation_type_id="ct", complex_relation_type_name="T",
             relation_type_id="rt", relation_role="source", asset_id="a1"),
        dict(complex_relation_id="cr1", complex_relation_type_id="ct", complex_relation_type_name="T",
             relation_type_id="rt", relation_role="target", asset_id="a2"),
    ])
    write_table(tmp_path, "responsibility", [dict(
        role_id="ro", role_name="Owner", asset_id="a1", user_id="u1", username="jdoe", user_firstname="Jane",
        user_lastname="Doe", user_email="j@x.com", user_language="en", user_licensetype="AUTHOR",
        is_user_guest=False, is_user_api=False, is_user_activated=True, is_user_enabled=True,
        is_responsibility_system=False, group_id=None, group_name=None, creation_date=None, edited_date=None)])
    write_table(tmp_path, "view_events", [dict(
        event_id="e1", user_id="u1", username="jdoe", event_time=dt.datetime(2026, 10, 10, 9, 0), session_id="s1",
        asset_id="a1", asset_full_name="f", asset_display_name="n", domain_id="d1", domain_name="Dom",
        community_id="c1", community_name="Root", diagram_id=None, diagram_name=None, dashboard_id=None,
        dashboard_name=None, view_id=None, view_name=None, page_parameters=None, page_path="/asset/a1", tab_name="Overview")])
    return Snapshot(tmp_path)


@pytest.fixture
def lake(tmp_path_factory):
    """An output folder that is NOT the snapshot folder (they must stay separate)."""
    return tmp_path_factory.mktemp("lake")

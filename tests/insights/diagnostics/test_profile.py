"""The catalogue profile: aggregates and vocabulary only, latest snapshot, changes between the last two."""

import datetime as dt

from collibra_toolkit.insights.diagnostics.profile import CAPABILITIES, _capability_case, profile_report
from collibra_toolkit.insights.store import Snapshot
from tests.insights.helpers import write_fixture_snapshot, write_table


def test_profile_has_every_section_and_no_personal_or_content_names(snap):
    text = profile_report(snap)
    for title in ("catalogue at a glance", "capabilities in use", "asset types", "domain types", "statuses",
                  "how richly described", "attribute types in use", "relation patterns", "roles on real assets",
                  "responsibility concentration", "tags", "freshness", "contributors", "changes between",
                  "scope: what to exclude", "statuses by asset type", "attributes filled on business glossary types"):
        assert f"## {title}" in text, title
    for forbidden in ("jdoe", "Jane", "j@x.com", "Dom |", "Root |", "Parent"):
        assert forbidden not in text
    assert "assets: 2" in text and "one snapshot loaded" in text


def test_capability_grouping_is_ordered_and_visible(snap):
    rows = dict(snap.sql(f"""SELECT t, {_capability_case('t')} FROM (VALUES ('Business Term'), ('Business Process'),
        ('Data Quality Metric'), ('Column'), ('BI Report'), ('Code Value'), ('Issue Category'), ('Mystery'),
        ('Data Quality Rule'), ('Adaptive Rule Score')) v(t)""").fetchall())
    assert rows == {"Business Term": "Business glossary", "Business Process": "Privacy & risk",
                    "Data Quality Metric": "Data quality", "Column": "Technical catalog", "BI Report": "BI & reporting",
                    "Code Value": "Reference data", "Issue Category": "Issue management", "Mystery": "Other",
                    "Data Quality Rule": "Data quality", "Adaptive Rule Score": "Data quality"}
    assert len({label for label, _ in CAPABILITIES}) == len(CAPABILITIES)


def test_profile_describes_only_the_latest_snapshot_and_reports_changes(tmp_path):
    write_fixture_snapshot(tmp_path / "insights-2026-10-10", dt.date(2026, 10, 10))
    later = dt.date(2026, 10, 11)
    write_fixture_snapshot(tmp_path / "insights-2026-10-11", later)
    write_table(tmp_path / "insights-2026-10-11", "asset", [dict(
        asset_id="a3", domain_id="d1", asset_full_name="f3", asset_display_name="n3", asset_type_id="at",
        asset_type_name="Term", status_id="s", status_name="Candidate", articulation=0.0, ratings_average=0.0,
        ratings_count=0, is_asset_system=False, creation_date=None, edited_date=None,
        creator_username="jdoe", editor_username="jdoe")], later, name="extra.parquet")
    text = profile_report(Snapshot(tmp_path))
    assert "snapshot_date: 2026-10-11" in text and "assets: 3" in text      # latest photo only, not 2 + 3
    assert "previous: 2026-10-10 | current: 2026-10-11" in text
    assert "assets added: 1" in text and "assets removed: 0" in text


def test_collibra_operating_model_is_recognised_by_domain_type(snap):
    case = _capability_case("t", "dt")
    rows = snap.sql(f"SELECT {case} FROM (VALUES ('Domain', 'Operating Model Dictionary'), ('Business Term', 'Glossary')) v(t, dt)").fetchall()
    assert rows == [("Collibra operating model",), ("Business glossary",)]


def test_scope_and_glossary_sections_on_the_fixture(snap):
    text = profile_report(snap)
    assert "business_assets_in_scope: 2" in text and "collibra_operating_model_assets: 0" in text
    assert "structural_relations: 0" in text and "semantic_relations: 1" in text
    assert "Term | Definition | 1 | 2 | 50.0" in text
    assert "## traceability" in text and "Term | 2 | 0 | 0 | 0 | 2" in text   # the fixture links two terms to each other only

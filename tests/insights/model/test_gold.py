"""Gold tables: additive counts driven by a client config, privacy by default."""

import shutil

from collibra_toolkit.insights.model import GoldConfig, build_gold
from collibra_toolkit.insights.store import Snapshot

CFG = GoldConfig(governed_types=("Term",))   # the fixture's asset type


def test_gold_products_are_created(snap):
    assert build_gold(snap, CFG) == [
        "gold_catalog_inventory", "gold_governance_scorecard", "gold_stewardship_workload",
        "gold_asset_connectivity", "gold_usage_daily",
    ]


def test_scorecard_counts_follow_the_config(snap):
    build_gold(snap, CFG)
    rows = snap.sql("""SELECT domain_name, assets, with_definition, with_owner, connected, approved, stale
                       FROM gold_governance_scorecard ORDER BY domain_name NULLS LAST""").fetchall()
    # a1 (domain 'Dom') has a definition, an owner, a relation and is Approved; a2 (domain missing from the export) only the last two
    assert rows == [("Dom", 1, 1, 1, 1, 1, 0), (None, 1, 0, 0, 1, 1, 0)]

    build_gold(snap, GoldConfig(governed_types=("Term",), approved_statuses=("Candidate",), owner_roles=("Steward",)))
    row = snap.sql("SELECT sum(approved), sum(with_owner) FROM gold_governance_scorecard").fetchone()
    assert row == (0, 0)                                   # other names, other answer: nothing is hardcoded

    build_gold(snap, GoldConfig(governed_types=("Nope",)))
    assert snap.sql("SELECT count(*) FROM gold_governance_scorecard").fetchone() == (0,)


def test_config_values_cannot_break_the_sql(snap):
    build_gold(snap, GoldConfig(governed_types=("O'Neil",), owner_roles=("Bob's role",), definition_attribute="it's"))
    assert snap.sql("SELECT count(*) FROM gold_governance_scorecard").fetchone() == (0,)


def test_other_products(snap):
    build_gold(snap, CFG)
    assert snap.sql("SELECT asset_type_name, assets, connected_assets, relation_endpoints FROM gold_asset_connectivity").fetchall() == [("Term", 2, 2, 2)]
    assert snap.sql("SELECT sum(assets) FROM gold_catalog_inventory").fetchone() == (2,)
    assert snap.sql("SELECT active_users, views FROM gold_usage_daily").fetchall() == [(1, 1)]


def test_usernames_are_off_unless_asked(snap):
    build_gold(snap, CFG)
    cols = [c[0] for c in snap.describe("gold_stewardship_workload")]
    assert "user_id" in cols and "username" not in cols
    assert snap.sql("SELECT role_name, assets, domains FROM gold_stewardship_workload").fetchall() == [("Owner", 1, 1)]
    build_gold(snap, GoldConfig(governed_types=("Term",), include_usernames=True))
    assert "username" in [c[0] for c in snap.describe("gold_stewardship_workload")]


def test_usage_product_only_exists_with_view_events(snap, tmp_path_factory):
    root = tmp_path_factory.mktemp("noviews")
    for src in snap.path.iterdir():
        if src.name != "view_events":
            shutil.copytree(src, root / src.name)
    assert "gold_usage_daily" not in build_gold(Snapshot(root), CFG)

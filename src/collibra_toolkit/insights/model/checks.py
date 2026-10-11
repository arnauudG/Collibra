"""Conformance checks over the model: counts of violations, 0 = clean."""

from __future__ import annotations

from ..store import Snapshot
from .views import build_model

_CHECKS = {
    "asset_missing_domain": "SELECT count(*) FROM asset a LEFT JOIN domain d USING (snapshot_date, domain_id) WHERE d.domain_id IS NULL",
    "domain_missing_community": "SELECT count(*) FROM domain d LEFT JOIN community c USING (snapshot_date, community_id) WHERE c.community_id IS NULL",
    "attribute_missing_asset": "SELECT count(*) FROM attribute t LEFT JOIN asset a USING (snapshot_date, asset_id) WHERE t.asset_id IS NOT NULL AND a.asset_id IS NULL",
    "asset_tag_missing_asset": "SELECT count(*) FROM asset_tag t LEFT JOIN asset a USING (snapshot_date, asset_id) WHERE a.asset_id IS NULL",
    # responsibilities may sit on domains/communities too ("a given resource"), so nonzero is informational
    "responsibility_missing_asset": "SELECT count(*) FROM responsibility t LEFT JOIN asset a USING (snapshot_date, asset_id) WHERE t.asset_id IS NOT NULL AND a.asset_id IS NULL",
    "relation_missing_asset": "SELECT count(*) FROM fact_relation r LEFT JOIN asset a1 ON a1.snapshot_date = r.snapshot_date AND a1.asset_id = r.asset_id1 LEFT JOIN asset a2 ON a2.snapshot_date = r.snapshot_date AND a2.asset_id = r.asset_id2 WHERE a1.asset_id IS NULL OR a2.asset_id IS NULL",
    "relation_ids_not_stored_twice": "SELECT count(*) FROM (SELECT 1 FROM relation GROUP BY snapshot_date, relation_id HAVING count(*) <> 2)",
    "community_parent_mismatch": "SELECT count(*) FROM community c JOIN (SELECT snapshot_date, community_id, max(level) AS d FROM community GROUP BY 1, 2) m USING (snapshot_date, community_id) WHERE c.level = m.d - 1 AND c.level_community_id IS DISTINCT FROM c.parent_community_id",
    "dim_asset_duplicate_keys": "SELECT count(*) - count(DISTINCT (snapshot_date, asset_id)) FROM dim_asset",
    "dim_community_duplicate_keys": "SELECT count(*) - count(DISTINCT (snapshot_date, community_id)) FROM dim_community",
}


def check_model(snap: Snapshot) -> dict[str, int]:
    """Row counts of conformance violations (0 = clean). Builds the model if needed."""
    build_model(snap)
    return {name: snap.con.execute(sql).fetchone()[0] for name, sql in _CHECKS.items()}

"""Star-schema views over a Snapshot. See docs/insights/modeling.md for the reasoning.

Every view keeps ``snapshot_date`` so several snapshots can be loaded side by side;
joins therefore always match on (snapshot_date, id).
"""

from __future__ import annotations

from .snapshot import Snapshot

_USER_PII = "user_firstname, user_lastname, user_email,"

_VIEWS = [
    # community rows repeat once per hierarchy level (357 rows / 187 ids observed)
    ("dim_community", """
        SELECT DISTINCT ON (snapshot_date, community_id)
               snapshot_date, community_id, community_name, community_description,
               is_community_system, uri AS community_uri, parent_community_id,
               max(level) OVER (PARTITION BY snapshot_date, community_id) AS depth,
               parent_community_id IS NULL AS is_root
        FROM community ORDER BY snapshot_date, community_id, level"""),
    # one row per community per level: level 1 = root ... level depth = the community itself
    ("bridge_community_ancestor", """
        SELECT snapshot_date, community_id, level AS ancestor_level,
               level_community_id AS ancestor_community_id, level_community_name AS ancestor_name
        FROM community"""),
    ("dim_domain", """
        SELECT d.snapshot_date, d.domain_id, d.domain_name, d.domain_description,
               d.domain_type_id, d.domain_type_name, d.is_domain_system,
               d.community_id, c.community_name
        FROM domain d
        LEFT JOIN dim_community c ON c.snapshot_date = d.snapshot_date AND c.community_id = d.community_id"""),
    # LEFT JOIN on purpose: some assets reference a domain absent from the export (14 observed)
    ("dim_asset", """
        SELECT a.snapshot_date, a.asset_id, a.asset_full_name, a.asset_display_name,
               a.asset_type_id, a.asset_type_name, a.status_id, a.status_name,
               a.articulation, a.ratings_average, a.ratings_count, a.is_asset_system,
               a.creation_date, a.edited_date, a.creator_username, a.editor_username,
               a.domain_id, d.domain_name, d.domain_type_name, d.community_id, d.community_name,
               (d.domain_id IS NULL) AS is_domain_missing
        FROM asset a
        LEFT JOIN dim_domain d ON d.snapshot_date = a.snapshot_date AND d.domain_id = a.domain_id"""),
    ("dim_snapshot", """
        SELECT DISTINCT snapshot_date, year(snapshot_date) AS year, month(snapshot_date) AS month,
               day(snapshot_date) AS day, snapshot_date = last_day(snapshot_date) AS is_month_end
        FROM asset"""),
    ("fact_attribute", """
        SELECT snapshot_date, attribute_id, asset_id, complex_relation_id,
               attribute_type_id, attribute_type_name, kind,
               expression_long, numeric_value, boolean_value, datetime_value,
               coalesce(expression_long, CAST(numeric_value AS VARCHAR),
                        CAST(boolean_value AS VARCHAR), CAST(datetime_value AS VARCHAR)) AS value_as_text,
               edited_date
        FROM attribute"""),
    # every relation is stored twice (head -> tail and tail -> head): keep one
    ("fact_relation", """
        SELECT snapshot_date, relation_id, relation_type_id, role_or_corole,
               asset_id1, asset_type_id1, asset_type_name1,
               asset_id2, asset_type_id2, asset_type_name2, is_relation_generated
        FROM relation WHERE direction = 'head -> tail'"""),
    # asset_resolution: ~25% of rows point at built-in "meta" objects the export omits; keep them, label them
    ("fact_responsibility", """
        SELECT r.snapshot_date, r.role_id, r.role_name, r.asset_id, r.user_id, r.group_id, r.group_name,
               CASE WHEN r.asset_id IS NULL THEN 'no_asset_id'
                    WHEN EXISTS (SELECT 1 FROM asset a WHERE a.snapshot_date = r.snapshot_date AND a.asset_id = r.asset_id)
                         THEN 'in_export' ELSE 'not_in_export' END AS asset_resolution,
               r.is_responsibility_system, r.creation_date, r.edited_date
        FROM responsibility r"""),
    ("bridge_asset_tag", """
        SELECT snapshot_date, asset_id, tag_id, tag_name FROM asset_tag"""),
    # one row per participant of a complex relation (~2 per id observed)
    ("bridge_complex_relation", """
        SELECT snapshot_date, complex_relation_id, complex_relation_type_id, complex_relation_type_name,
               relation_type_id, relation_role, asset_id
        FROM complex_relation"""),
]

_DIM_USER = """
    SELECT DISTINCT ON (snapshot_date, user_id)
           snapshot_date, user_id, username, {pii}
           user_language, user_licensetype, is_user_guest, is_user_api,
           is_user_activated, is_user_enabled
    FROM responsibility WHERE user_id IS NOT NULL
    ORDER BY snapshot_date, user_id"""

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


def build_model(snap: Snapshot, include_pii: bool = False) -> list[str]:
    """Create the model views in the snapshot's DuckDB session; return their names.

    ``dim_user`` is derived from ``responsibility`` (there is no user table). By default it
    omits first name, last name and email; pass ``include_pii=True`` to keep them.
    """
    absent = snap.missing()
    if absent:
        raise ValueError(f"snapshot lacks tables needed for the model: {', '.join(absent)}")
    views = _VIEWS + [("dim_user", _DIM_USER.format(pii=_USER_PII if include_pii else ""))]
    if "view_events" in snap.tables:  # optional table; documented columns, passed through untouched
        views.append(("fact_view_event", "SELECT * FROM view_events"))
    for name, sql in views:
        snap.con.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")
    return [name for name, _ in views]


def check_model(snap: Snapshot) -> dict[str, int]:
    """Row counts of conformance violations (0 = clean). Builds the model if needed."""
    build_model(snap)
    return {name: snap.con.execute(sql).fetchone()[0] for name, sql in _CHECKS.items()}


__all__ = ["build_model", "check_model"]

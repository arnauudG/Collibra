"""What a catalogue contains and says: an aggregate profile of the latest snapshot.

Prints counts plus operating-model vocabulary (asset, attribute, domain-type, role, status and tag
names); never asset, domain, community or person names. When several snapshots are loaded it also
compares the last two. Needs a Snapshot and the model; no network.
"""

from __future__ import annotations

from ..model import build_model
from ..store import Snapshot

# Views restricted to the latest snapshot, so every section describes one photo.
_CURRENT = [
    "dim_asset", "dim_domain", "dim_community", "fact_attribute", "fact_relation", "fact_responsibility",
    "bridge_asset_tag", "bridge_complex_relation",
]

# Heuristic grouping of asset types into Collibra capabilities, by type name. First match wins.
OPERATING_MODEL_DOMAIN_TYPE = "Operating Model Dictionary"  # Collibra's own configuration, exported as assets

# Heuristic grouping of asset types into Collibra capabilities, by type name. First match wins, so the
# specific families come before the broad ones (e.g. "Data Quality Rule" is data quality, not a policy).
CAPABILITIES: list[tuple[str, list[str]]] = [
    ("AI governance", ["AI %", "% AI %", "%Model Card%"]),
    ("Data products", ["%Data Product%"]),
    ("Data quality", ["%Data Quality%", "%Adaptive%", "%Quality%", "%Metric%"]),
    ("Privacy & risk", ["%Business Process%", "%Third Party%", "%Regulation%", "%Legal%", "%Privacy%",
                        "%Processing%", "%Data Subject%", "%Risk%", "%Assessment%"]),
    ("Policies & rules", ["%Policy%", "%Rule%", "%Standard%", "%Control%"]),
    ("Reference data", ["%Code%", "%Reference%", "%Value List%"]),
    ("BI & reporting", ["%Report%", "BI %", "%Tableau%", "%Power BI%", "%Dashboard%"]),
    ("Issue management", ["%Issue%"]),
    ("Technical catalog", ["%Table%", "%Column%", "%Schema%", "%Database%", "%Data Set%", "%File%", "%Storage%",
                           "%System%", "%Server%", "%Data Element%", "%Data Structure%", "%Data Attribute%",
                           "%Data Entity%", "%Field%", "%Data Model%", "%Data Usage%"]),
    ("Business glossary", ["%Term%", "%Acronym%", "%KPI%", "%Business Dimension%", "%Measure%", "%Glossary%"]),
]

# Statuses that mean "no longer live" (heuristic); exclude them before computing KPIs.
TERMINAL_STATUSES = ("Removed", "Missing from source", "Obsolete", "Retired", "Deprecated", "Rejected", "Archived")
# Relation roles that express containment or typing rather than business meaning (heuristic).
STRUCTURAL_ROLES = ("is part of", "contains", "is of type", "groups", "assigned to", "has")


def _capability_case(type_col: str, domain_type_col: str | None = None) -> str:
    whens = []
    if domain_type_col:
        whens.append(f"WHEN {domain_type_col} = '{OPERATING_MODEL_DOMAIN_TYPE}' THEN 'Collibra operating model'")
    for label, patterns in CAPABILITIES:
        cond = " OR ".join(f"{type_col} ILIKE '{p}'" for p in patterns)
        whens.append(f"WHEN {cond} THEN '{label}'")
    return "CASE " + " ".join(whens) + " ELSE 'Other' END"


def _sql_list(values: tuple[str, ...]) -> str:
    return "(" + ", ".join("'" + v.replace("'", "''") + "'" for v in values) + ")"


CAP = _capability_case("asset_type_name", "domain_type_name")

SECTIONS: list[tuple[str, str]] = [
    ("catalogue at a glance (latest snapshot)", """
        SELECT (SELECT max(snapshot_date) FROM dim_snapshot) AS snapshot_date,
               (SELECT count(*) FROM cur_dim_community) AS communities,
               (SELECT count(*) FROM cur_dim_domain) AS domains,
               (SELECT count(DISTINCT domain_id) FROM cur_dim_asset WHERE NOT is_domain_missing) AS domains_with_assets,
               (SELECT count(*) FROM cur_dim_asset) AS assets,
               (SELECT count(DISTINCT asset_type_name) FROM cur_dim_asset) AS asset_types_used,
               (SELECT count(*) FROM cur_fact_attribute) AS attribute_values,
               (SELECT count(DISTINCT attribute_type_name) FROM cur_fact_attribute) AS attribute_types_used,
               (SELECT count(*) FROM cur_fact_relation) AS relations,
               (SELECT count(DISTINCT relation_type_id) FROM cur_fact_relation) AS relation_types_used,
               (SELECT count(DISTINCT complex_relation_id) FROM cur_bridge_complex_relation) AS complex_relations,
               (SELECT count(*) FROM cur_fact_responsibility WHERE asset_resolution = 'in_export') AS responsibilities_on_assets,
               (SELECT count(DISTINCT tag_name) FROM cur_bridge_asset_tag) AS distinct_tags,
               (SELECT count(DISTINCT asset_id) FROM cur_bridge_asset_tag) AS tagged_assets"""),
    ("capabilities in use (heuristic grouping of asset types by name)", f"""
        SELECT {CAP} AS capability,
               count(DISTINCT asset_type_name) AS asset_types, count(*) AS assets,
               round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_of_assets
        FROM cur_dim_asset GROUP BY 1 ORDER BY 3 DESC"""),
    ("scope: what to exclude before computing KPIs (heuristic)", f"""
        SELECT count(*) AS assets,
               sum(CASE WHEN domain_type_name = '{OPERATING_MODEL_DOMAIN_TYPE}' THEN 1 ELSE 0 END) AS collibra_operating_model_assets,
               sum(CASE WHEN status_name IN {_sql_list(TERMINAL_STATUSES)} THEN 1 ELSE 0 END) AS assets_in_a_terminal_status,
               sum(CASE WHEN domain_type_name IS DISTINCT FROM '{OPERATING_MODEL_DOMAIN_TYPE}'
                         AND status_name NOT IN {_sql_list(TERMINAL_STATUSES)} THEN 1 ELSE 0 END) AS business_assets_in_scope,
               (SELECT count(*) FROM cur_fact_relation WHERE role_or_corole IN {_sql_list(STRUCTURAL_ROLES)}) AS structural_relations,
               (SELECT count(*) FROM cur_fact_relation WHERE role_or_corole NOT IN {_sql_list(STRUCTURAL_ROLES)}) AS semantic_relations,
               (SELECT count(*) FROM cur_fact_attribute WHERE asset_id IS NULL) AS attribute_values_on_complex_relations
        FROM cur_dim_asset"""),
    ("asset types: where the content is (top 20)", f"""
        SELECT asset_type_name, {CAP} AS capability, count(*) AS assets,
               round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct,
               count(DISTINCT domain_id) AS domains, count(DISTINCT community_id) AS communities
        FROM cur_dim_asset GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20"""),
    ("long tail of asset types", """
        WITH t AS (SELECT asset_type_name, count(*) AS n FROM cur_dim_asset GROUP BY 1)
        SELECT count(*) AS asset_types_used, sum(CASE WHEN n <= 5 THEN 1 ELSE 0 END) AS with_5_or_fewer_assets,
               sum(CASE WHEN n = 1 THEN 1 ELSE 0 END) AS with_1_asset,
               round(100.0 * max(n) / sum(n), 1) AS pct_in_largest_type
        FROM t"""),
    ("domain types: how the catalogue is organised (top 15)", """
        SELECT d.domain_type_name, count(DISTINCT d.domain_id) AS domains,
               count(DISTINCT a.domain_id) AS domains_with_assets, count(a.asset_id) AS assets
        FROM cur_dim_domain d LEFT JOIN cur_dim_asset a ON a.domain_id = d.domain_id
        GROUP BY 1 ORDER BY 4 DESC LIMIT 15"""),
    ("structure: community depth and domain size", """
        WITH s AS (SELECT domain_id, count(*) AS n FROM cur_dim_asset WHERE NOT is_domain_missing GROUP BY 1)
        SELECT (SELECT max(depth) FROM cur_dim_community) AS deepest_community_level,
               (SELECT count(*) FROM cur_dim_community WHERE is_root) AS top_level_communities,
               quantile_cont(n, 0.5) AS median_assets_per_domain,
               quantile_cont(n, 0.9) AS p90_assets_per_domain,
               max(n) AS largest_domain
        FROM s"""),
    ("statuses (top 12)", """
        SELECT status_name, count(*) AS assets, round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
        FROM cur_dim_asset GROUP BY 1 ORDER BY 2 DESC LIMIT 12"""),
    ("statuses by asset type (the 8 largest types)", """
        WITH top AS (SELECT asset_type_name FROM cur_dim_asset GROUP BY 1 ORDER BY count(*) DESC LIMIT 8)
        SELECT a.asset_type_name, a.status_name, count(*) AS assets
        FROM cur_dim_asset a JOIN top USING (asset_type_name)
        GROUP BY 1, 2 ORDER BY 1, 3 DESC"""),
    ("how richly described, by asset type (top 12)", """
        WITH per AS (
            SELECT a.asset_type_name, a.asset_id, count(t.attribute_id) AS n
            FROM cur_dim_asset a LEFT JOIN cur_fact_attribute t ON t.asset_id = a.asset_id
            GROUP BY 1, 2)
        SELECT asset_type_name, count(*) AS assets, round(avg(n), 1) AS avg_attributes,
               round(100.0 * sum(CASE WHEN n = 0 THEN 1 ELSE 0 END) / count(*), 1) AS pct_without_any_attribute
        FROM per GROUP BY 1 ORDER BY 2 DESC LIMIT 12"""),
    ("attribute types in use (top 20)", """
        SELECT attribute_type_name, kind, count(*) AS attribute_values, count(DISTINCT asset_id) AS assets
        FROM cur_fact_attribute GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20"""),
    ("attributes filled on business glossary types (top 25)", f"""
        WITH g AS (SELECT asset_id, asset_type_name FROM cur_dim_asset WHERE {CAP} = 'Business glossary'),
        n AS (SELECT asset_type_name, count(*) AS total FROM g GROUP BY 1)
        SELECT g.asset_type_name, t.attribute_type_name, count(DISTINCT t.asset_id) AS assets_with_it, n.total AS assets,
               round(100.0 * count(DISTINCT t.asset_id) / n.total, 1) AS pct
        FROM g
        JOIN cur_fact_attribute t ON t.asset_id = g.asset_id AND coalesce(t.value_as_text, '') <> ''
        JOIN n ON n.asset_type_name = g.asset_type_name
        GROUP BY 1, 2, 4 ORDER BY 1, 3 DESC LIMIT 25"""),
    ("relation patterns, one direction (top 20)", """
        SELECT asset_type_name1 AS head_type, role_or_corole AS role, asset_type_name2 AS tail_type, count(*) AS relations
        FROM cur_fact_relation GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT 20"""),
    ("traceability: what business glossary assets are linked to (any relation, either direction)", f"""
        WITH cap AS (SELECT asset_id, asset_type_name, {CAP} AS capability FROM cur_dim_asset),
        links AS (SELECT asset_id1 AS a, asset_id2 AS b FROM cur_fact_relation
                  UNION ALL SELECT asset_id2, asset_id1 FROM cur_fact_relation),
        linked AS (SELECT DISTINCT l.a AS asset_id, c2.capability AS linked_capability
                   FROM links l JOIN cap c2 ON c2.asset_id = l.b)
        SELECT c.asset_type_name, count(DISTINCT c.asset_id) AS assets,
               count(DISTINCT CASE WHEN k.linked_capability = 'Technical catalog' THEN c.asset_id END) AS linked_to_technical_catalog,
               count(DISTINCT CASE WHEN k.linked_capability = 'BI & reporting' THEN c.asset_id END) AS linked_to_bi,
               count(DISTINCT CASE WHEN k.linked_capability = 'Data quality' THEN c.asset_id END) AS linked_to_data_quality,
               count(DISTINCT CASE WHEN k.linked_capability = 'Business glossary' THEN c.asset_id END) AS linked_to_other_glossary_assets
        FROM cap c LEFT JOIN linked k ON k.asset_id = c.asset_id
        WHERE c.capability = 'Business glossary'
        GROUP BY 1 ORDER BY 2 DESC"""),
    ("connectedness by asset type (top 12)", """
        WITH ends AS (SELECT asset_id1 AS asset_id FROM cur_fact_relation UNION ALL SELECT asset_id2 FROM cur_fact_relation),
        deg AS (SELECT asset_id, count(*) AS d FROM ends GROUP BY 1)
        SELECT a.asset_type_name, count(*) AS assets,
               round(100.0 * count(g.asset_id) / count(*), 1) AS pct_connected,
               round(avg(coalesce(g.d, 0)), 1) AS avg_relations, max(coalesce(g.d, 0)) AS max_relations
        FROM cur_dim_asset a LEFT JOIN deg g ON g.asset_id = a.asset_id
        GROUP BY 1 ORDER BY 2 DESC LIMIT 12"""),
    ("complex relation types (top 10)", """
        SELECT complex_relation_type_name, count(DISTINCT complex_relation_id) AS relations, count(*) AS legs
        FROM cur_bridge_complex_relation GROUP BY 1 ORDER BY 2 DESC LIMIT 10"""),
    ("roles on real assets (top 12)", """
        SELECT role_name, count(*) AS assignments, count(DISTINCT asset_id) AS assets,
               count(DISTINCT coalesce(user_id, group_id)) AS holders
        FROM cur_fact_responsibility WHERE asset_resolution = 'in_export'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 12"""),
    ("responsibility coverage by asset type (top 12)", """
        WITH r AS (SELECT DISTINCT asset_id, role_name FROM cur_fact_responsibility WHERE asset_resolution = 'in_export')
        SELECT a.asset_type_name, count(DISTINCT a.asset_id) AS assets,
               round(100.0 * count(DISTINCT r.asset_id) / count(DISTINCT a.asset_id), 1) AS pct_with_any_responsibility,
               count(DISTINCT r.role_name) AS roles_used
        FROM cur_dim_asset a LEFT JOIN r ON r.asset_id = a.asset_id
        GROUP BY 1 ORDER BY 2 DESC LIMIT 12"""),
    ("responsibility concentration (people, not groups)", """
        WITH h AS (SELECT user_id, count(*) AS n FROM cur_fact_responsibility
                   WHERE asset_resolution = 'in_export' AND user_id IS NOT NULL GROUP BY 1),
        r AS (SELECT n, row_number() OVER (ORDER BY n DESC) AS rk FROM h)
        SELECT count(*) AS people, sum(n) AS assignments,
               round(100.0 * sum(CASE WHEN rk <= 1 THEN n END) / sum(n), 1) AS pct_held_by_top_1,
               round(100.0 * sum(CASE WHEN rk <= 5 THEN n END) / sum(n), 1) AS pct_held_by_top_5,
               round(100.0 * sum(CASE WHEN rk <= 10 THEN n END) / sum(n), 1) AS pct_held_by_top_10,
               quantile_cont(n, 0.5) AS median_per_person
        FROM r"""),
    ("tags (top 10)", """
        SELECT tag_name, count(DISTINCT asset_id) AS assets FROM cur_bridge_asset_tag GROUP BY 1 ORDER BY 2 DESC LIMIT 10"""),
    ("freshness", """
        SELECT round(100.0 * avg(CASE WHEN edited_date >= snapshot_date - INTERVAL 30 DAY THEN 1 ELSE 0 END), 1) AS pct_edited_last_30_days,
               round(100.0 * avg(CASE WHEN edited_date >= snapshot_date - INTERVAL 90 DAY THEN 1 ELSE 0 END), 1) AS pct_edited_last_90_days,
               round(100.0 * avg(CASE WHEN edited_date >= snapshot_date - INTERVAL 365 DAY THEN 1 ELSE 0 END), 1) AS pct_edited_last_365_days,
               round(100.0 * avg(CASE WHEN edited_date IS NULL THEN 1 ELSE 0 END), 1) AS pct_without_edit_date
        FROM cur_dim_asset"""),
    ("assets by year created", """
        SELECT year(CAST(creation_date AS TIMESTAMP)) AS year_created, count(*) AS assets
        FROM cur_dim_asset GROUP BY 1 ORDER BY 1"""),
    ("contributors (counts only)", """
        WITH c AS (SELECT creator_username AS who, count(*) AS n FROM cur_dim_asset WHERE creator_username IS NOT NULL GROUP BY 1),
        r AS (SELECT n, row_number() OVER (ORDER BY n DESC) AS rk FROM c)
        SELECT count(*) AS distinct_creators,
               round(100.0 * sum(CASE WHEN rk <= 1 THEN n END) / sum(n), 1) AS pct_created_by_top_1,
               round(100.0 * sum(CASE WHEN rk <= 5 THEN n END) / sum(n), 1) AS pct_created_by_top_5,
               (SELECT count(DISTINCT editor_username) FROM cur_dim_asset) AS distinct_last_editors
        FROM r"""),
]


# Single-row summaries, printed one "name: value" per line.
_SUMMARIES = ("catalogue at a glance", "scope", "long tail", "structure", "responsibility concentration", "freshness", "contributors")


def _render(snap: Snapshot, title: str, sql: str) -> str:
    cur = snap.sql(sql)
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    fmt = lambda v: "" if v is None else str(v)  # noqa: E731
    if title.startswith(_SUMMARIES) and len(rows) == 1:
        body = [f"{c}: {fmt(v)}" for c, v in zip(cols, rows[0])]
    else:
        body = [" | ".join(cols)] + [" | ".join(fmt(v) for v in r) for r in rows] if rows else ["(no rows)"]
    return "\n".join([f"## {title}", *body])


def _changes(snap: Snapshot) -> str:
    dates = [r[0] for r in snap.sql("SELECT snapshot_date FROM dim_snapshot ORDER BY 1").fetchall()]
    title = "## changes between the last two snapshots"
    if len(dates) < 2:
        return f"{title}\n(one snapshot loaded: point `profile` at a folder holding two or more to see changes)"
    prev, cur = (d.isoformat() for d in dates[-2:])
    q = lambda sql: snap.sql(sql).fetchone()[0]  # noqa: E731
    count = lambda view, day: q(f"SELECT count(*) FROM {view} WHERE snapshot_date = DATE '{day}'")  # noqa: E731
    lines = [title, f"previous: {prev} | current: {cur}"]
    lines.append("assets added: " + str(q(f"""SELECT count(*) FROM dim_asset b WHERE b.snapshot_date = DATE '{cur}'
        AND NOT EXISTS (SELECT 1 FROM dim_asset a WHERE a.snapshot_date = DATE '{prev}' AND a.asset_id = b.asset_id)""")))
    lines.append("assets removed: " + str(q(f"""SELECT count(*) FROM dim_asset a WHERE a.snapshot_date = DATE '{prev}'
        AND NOT EXISTS (SELECT 1 FROM dim_asset b WHERE b.snapshot_date = DATE '{cur}' AND b.asset_id = a.asset_id)""")))
    lines.append("assets whose status changed: " + str(q(f"""SELECT count(*) FROM dim_asset a JOIN dim_asset b
        ON b.asset_id = a.asset_id AND a.snapshot_date = DATE '{prev}' AND b.snapshot_date = DATE '{cur}'
        WHERE a.status_name IS DISTINCT FROM b.status_name""")))
    lines.append("assets edited since the previous snapshot: " + str(q(f"""SELECT count(*) FROM dim_asset
        WHERE snapshot_date = DATE '{cur}' AND edited_date >= DATE '{prev}'""")))
    for view, label in (("fact_attribute", "attribute values"), ("fact_relation", "relations"),
                        ("fact_responsibility", "responsibilities")):
        before, after = count(view, prev), count(view, cur)
        lines.append(f"{label}: {before} -> {after} ({after - before:+d})")
    return "\n".join(lines)


def profile_report(snap: Snapshot) -> str:
    build_model(snap)
    for view in _CURRENT:
        snap.con.execute(
            f"CREATE OR REPLACE TEMP VIEW cur_{view} AS SELECT * FROM {view} "
            "WHERE snapshot_date = (SELECT max(snapshot_date) FROM dim_snapshot)"
        )
    header = ("# Catalogue profile\nAggregates plus operating-model vocabulary only (type, role, status, tag names); "
              "no asset, domain, community or person names. Skim tag names before sharing.")
    return "\n\n".join([header, *(_render(snap, t, s) for t, s in SECTIONS), _changes(snap)])

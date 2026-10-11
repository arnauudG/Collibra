"""Offline evidence about what an Insights export contains: aggregates only, never row content.

Needs a ``Snapshot`` and nothing else (no network). ``live.py`` adds the comparison with the REST API.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..store import Snapshot

# a responsibility whose asset_id is set but matches no exported asset
UNRESOLVED = """
    SELECT r.* FROM responsibility r
    LEFT JOIN asset a ON a.snapshot_date = r.snapshot_date AND a.asset_id = r.asset_id
    WHERE r.asset_id IS NOT NULL AND a.asset_id IS NULL"""

SECTIONS: list[tuple[str, str]] = [
    ("attribute kind -> which value column is filled", """
        SELECT kind, count(*) AS n, count(expression_long) AS has_text, count(numeric_value) AS has_numeric,
               count(boolean_value) AS has_boolean, count(datetime_value) AS has_date
        FROM attribute GROUP BY 1 ORDER BY 2 DESC"""),
    ("community.level: is each community's rows a root-to-self path?", """
        WITH m AS (
            SELECT community_id, count(*) AS rows_, max(level) AS maxl, min(level) AS minl,
                   any_value(parent_community_id) AS parent
            FROM community GROUP BY 1),
        s AS (
            SELECT c.community_id, bool_or(c.level_community_id = c.community_id AND c.level = m.maxl) AS self_at_max
            FROM community c JOIN m USING (community_id) GROUP BY 1)
        SELECT count(*) AS communities,
               sum((rows_ = maxl)::INT) AS rows_equal_deepest_level,
               sum((minl = 1)::INT) AS shallowest_level_is_1,
               sum(self_at_max::INT) AS own_row_at_deepest_level,
               sum((parent IS NULL)::INT) AS roots,
               max(maxl) AS deepest
        FROM m JOIN s USING (community_id)"""),
    ("Issue-related content present in the export", """
        SELECT 'asset' AS kind, asset_type_name AS type_name, count(*) AS n
        FROM asset WHERE asset_type_name ILIKE '%issue%' GROUP BY 2
        UNION ALL
        SELECT 'domain', domain_type_name, count(*) FROM domain WHERE domain_type_name ILIKE '%issue%' GROUP BY 2"""),
    ("assets whose domain is missing, by type", """
        SELECT a.asset_type_name, count(*) AS assets, count(DISTINCT a.domain_id) AS missing_domain_ids
        FROM asset a LEFT JOIN domain d ON d.snapshot_date = a.snapshot_date AND d.domain_id = a.domain_id
        WHERE d.domain_id IS NULL GROUP BY 1"""),
    ("responsibilities: overview", f"""
        WITH u AS ({UNRESOLVED})
        SELECT (SELECT count(*) FROM responsibility) AS total,
               (SELECT count(*) FROM responsibility WHERE asset_id IS NULL) AS null_asset_id,
               (SELECT count(*) FROM u) AS unresolved,
               (SELECT count(DISTINCT asset_id) FROM u) AS unresolved_distinct_ids,
               (SELECT count(*) FROM u WHERE user_id IS NOT NULL) AS held_by_user,
               (SELECT count(*) FROM u WHERE group_id IS NOT NULL) AS held_by_group"""),
    ("responsibilities: by role", """
        SELECT r.role_name, count(*) AS total,
               sum((r.asset_id IS NOT NULL AND a.asset_id IS NULL)::INT) AS unresolved
        FROM responsibility r
        LEFT JOIN asset a ON a.snapshot_date = r.snapshot_date AND a.asset_id = r.asset_id
        GROUP BY 1 ORDER BY 2 DESC"""),
    ("responsibilities: system-generated or not", """
        SELECT r.is_responsibility_system, count(*) AS total,
               sum((r.asset_id IS NOT NULL AND a.asset_id IS NULL)::INT) AS unresolved
        FROM responsibility r
        LEFT JOIN asset a ON a.snapshot_date = r.snapshot_date AND a.asset_id = r.asset_id
        GROUP BY 1"""),
    ("unresolved responsibilities: shape of the ids, per role", f"""
        SELECT role_name, count(*) AS rows_, count(DISTINCT asset_id) AS distinct_asset_ids,
               count(DISTINCT user_id) AS distinct_users, count(DISTINCT role_id) AS distinct_role_ids,
               sum((asset_id = user_id)::INT) AS asset_id_equals_user_id,
               sum((asset_id LIKE '00000000-%')::INT) AS system_style_ids
        FROM ({UNRESOLVED}) GROUP BY 1 ORDER BY 2 DESC"""),
    ("is_system flags in the export", """
        SELECT 'community' AS object, is_community_system AS is_system, count(DISTINCT community_id) AS n FROM community GROUP BY 2
        UNION ALL SELECT 'domain', is_domain_system, count(*) FROM domain GROUP BY 2
        UNION ALL SELECT 'asset', is_asset_system, count(*) FROM asset GROUP BY 2"""),
    ("domains with / without assets in the export (Collibra documents domains 'that contain assets')", """
        SELECT count(*) AS domains, sum((n = 0)::INT) AS without_assets,
               sum((n = 0 AND is_system)::INT) AS without_assets_and_system
        FROM (SELECT d.domain_id, d.is_domain_system AS is_system, count(a.asset_id) AS n
              FROM domain d LEFT JOIN asset a ON a.snapshot_date = d.snapshot_date AND a.domain_id = d.domain_id
              GROUP BY 1, 2)"""),
    ("exported domains by type (top 12)", """
        SELECT domain_type_name, count(*) AS n FROM domain GROUP BY 1 ORDER BY 2 DESC LIMIT 12"""),
    ("unresolved responsibility ids: where else do they appear?", f"""
        WITH u AS (SELECT DISTINCT asset_id AS id FROM ({UNRESOLVED}))
        SELECT (SELECT count(*) FROM u) AS ids,
               (SELECT count(*) FROM u WHERE id IN (SELECT asset_id FROM attribute)) AS in_attribute,
               (SELECT count(*) FROM u WHERE id IN (SELECT asset_id1 FROM relation UNION SELECT asset_id2 FROM relation)) AS in_relation,
               (SELECT count(*) FROM u WHERE id IN (SELECT asset_id FROM complex_relation)) AS in_complex_relation,
               (SELECT count(*) FROM u WHERE id IN (SELECT asset_id FROM asset_tag)) AS in_asset_tag,
               (SELECT count(*) FROM u WHERE id IN (SELECT domain_id FROM asset)) AS is_domain_of_an_asset,
               (SELECT count(*) FROM u WHERE id IN (SELECT domain_id FROM domain)) AS is_a_domain,
               (SELECT count(*) FROM u WHERE id IN (SELECT community_id FROM community)) AS is_a_community"""),
]


def layout(path: str | Path) -> str:
    """Real file layout: the explorer only reads .parquet, so check nothing else is hiding."""
    p = Path(path)
    ext = Counter(f.suffix or "(none)" for f in p.rglob("*") if f.is_file())
    tops = sorted(d.name for d in p.iterdir() if d.is_dir())
    return f"## file layout\ntop-level folders: {tops}\nfiles by extension: {dict(ext)}"


def _table(snap: Snapshot, title: str, sql: str) -> str:
    cur = snap.sql(sql)
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    body = [" | ".join("" if v is None else str(v) for v in r) for r in rows] or ["(no rows)"]
    return "\n".join([f"## {title}", " | ".join(cols), *body])


def snapshot_report(snap: Snapshot) -> str:
    parts = [layout(snap.path), f"## tables found\n{snap.tables}"]
    parts += [_table(snap, title, sql) for title, sql in SECTIONS]
    return "\n\n".join(parts)

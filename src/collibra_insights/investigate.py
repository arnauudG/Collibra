"""Evidence-gathering for open questions about what an Insights export contains.

Prints aggregates, ids and type names only, never row content. The ``live_*``
functions compare the export against the REST API of the same instance.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .client import CollibraClient, CollibraHTTPError, CollibraNotFound
from .explore import Snapshot

# a responsibility whose asset_id is set but matches no exported asset
_UNRESOLVED = """
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
        WITH u AS ({_UNRESOLVED})
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
    ("unresolved responsibility ids: where else do they appear?", f"""
        WITH u AS (SELECT DISTINCT asset_id AS id FROM ({_UNRESOLVED}))
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


# ---------------------------------------------------------------- live comparison


def _total(client: CollibraClient, path: str, **params) -> int | None:
    return client.get_json(path, {"limit": 1, "countLimit": -1, **params}).get("total")


def resolve_id(client: CollibraClient, id_: str) -> str:
    """Ask the live API what an id is. Returns the kind (and type name), never names."""
    for kind, path in (("asset", "/assets/"), ("domain", "/domains/"), ("community", "/communities/")):
        try:
            obj = client.get_json(path + id_)
        except CollibraNotFound:
            continue
        except CollibraHTTPError as exc:
            return f"{kind}? HTTP {exc.status_code}"
        type_name = (obj.get("type") or {}).get("name")
        return kind + (f" (type {type_name})" if type_name else "")
    return "not found as asset, domain or community"


def _ids(snap: Snapshot, sql: str, n: int = 8) -> list[str]:
    return [r[0] for r in snap.sql(f"SELECT DISTINCT id FROM ({sql}) ORDER BY id LIMIT {n}").fetchall()]


def live_report(client: CollibraClient, snap: Snapshot) -> str:
    out = ["## live vs export: totals"]
    snap_counts = {
        "communities": snap.sql("SELECT count(DISTINCT community_id) FROM community").fetchone()[0],
        "domains": snap.sql("SELECT count(DISTINCT domain_id) FROM domain").fetchone()[0],
        "assets": snap.sql("SELECT count(DISTINCT asset_id) FROM asset").fetchone()[0],
    }
    totals = {k: _total(client, f"/{k}") for k in snap_counts}
    out += [f"{k}: live {totals[k]} | export {snap_counts[k]}" for k in snap_counts]

    samples = {
        "unresolved responsibility ids": _ids(snap, f"SELECT asset_id AS id FROM ({_UNRESOLVED})"),
        "missing domain ids of orphan assets": _ids(
            snap,
            "SELECT a.domain_id AS id FROM asset a LEFT JOIN domain d ON d.snapshot_date = a.snapshot_date "
            "AND d.domain_id = a.domain_id WHERE d.domain_id IS NULL"),
        "domains whose community is missing": _ids(
            snap,
            "SELECT d.domain_id AS id FROM domain d LEFT JOIN community c ON c.snapshot_date = d.snapshot_date "
            "AND c.community_id = d.community_id WHERE c.community_id IS NULL"),
        "their (missing) community ids": _ids(
            snap,
            "SELECT d.community_id AS id FROM domain d LEFT JOIN community c ON c.snapshot_date = d.snapshot_date "
            "AND c.community_id = d.community_id WHERE c.community_id IS NULL"),
    }
    for title, ids in samples.items():
        out.append(f"\n## live lookup: {title} (sample of {len(ids)})")
        out += [f"{i[:8]}… -> {resolve_id(client, i)}" for i in ids] or ["(none)"]

    out.append("\n## live vs export: asset count per type (only types that differ)")
    live_types = list(client.paginate("/assetTypes", page_size=1000))
    snap_by_type = dict(snap.sql("SELECT asset_type_name, count(*) FROM asset GROUP BY 1").fetchall())
    rows, same_as_global = [], 0
    for t in live_types:
        live = _total(client, "/assets", typeIds=[t["id"]])
        if live and live == totals["assets"]:
            same_as_global += 1
        exp = snap_by_type.get(t["name"], 0)
        if live != exp:
            rows.append((t["name"], live, exp))
    if same_as_global >= 3:
        out.append("WARNING: the typeIds filter seems to be ignored (many types report the global total); "
                   "the per-type table below is NOT reliable.")
    rows.sort(key=lambda r: abs((r[1] or 0) - r[2]), reverse=True)
    out.append("type | live | export")
    out += [f"{n} | {a} | {b}" for n, a, b in rows[:40]] or ["(all types match)"]
    return "\n".join(out)

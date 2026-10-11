"""Evidence-gathering for open questions about what an Insights export contains.

Prints aggregates, ids and type names only, never row content. The ``live_*``
functions compare the export against the REST API of the same instance.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..client import CollibraClient, CollibraHTTPError, CollibraNotFound
from .snapshot import Snapshot

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
    ("unresolved responsibilities: shape of the ids, per role", f"""
        SELECT role_name, count(*) AS rows_, count(DISTINCT asset_id) AS distinct_asset_ids,
               count(DISTINCT user_id) AS distinct_users, count(DISTINCT role_id) AS distinct_role_ids,
               sum((asset_id = user_id)::INT) AS asset_id_equals_user_id,
               sum((asset_id LIKE '00000000-%')::INT) AS system_style_ids
        FROM ({_UNRESOLVED}) GROUP BY 1 ORDER BY 2 DESC"""),
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


def resolve_id(client: CollibraClient, id_: str, domain_types: dict[str, str] | None = None) -> str:
    """Ask the live API what an id is. Returns the kind, type and (for assets) the kind of domain it
    lives in, never names. ``domain_types`` maps exported domain ids to their type names."""
    for kind, path in (("asset", "/assets/"), ("domain", "/domains/"), ("community", "/communities/")):
        try:
            obj = client.get_json(path + id_)
        except CollibraNotFound:
            continue
        except CollibraHTTPError as exc:
            return f"{kind}? HTTP {exc.status_code}"
        label = kind
        type_name = (obj.get("type") or {}).get("name")
        if type_name:
            label += f" (type {type_name})"
        if kind == "asset" and domain_types is not None:
            dom = (obj.get("domain") or {}).get("id")
            if dom:
                label += f" in {domain_types[dom]} domain" if dom in domain_types else " in a domain not in the export"
        return label
    return "not found as asset, domain or community"


def probe_role(client: CollibraClient, role_id: str) -> str:
    """Ask the responsibilities API which kind of resource a role is attached to.

    Field names are tolerant on purpose (the schema was not verified): we report the item keys we
    saw, so a surprising answer is still informative.
    """
    try:
        page = client.get_json("/responsibilities", {"roleIds": [role_id], "limit": 20})
    except CollibraHTTPError as exc:
        return f"HTTP {exc.status_code}"
    items = page.get("results", [])
    if not items:
        return "no results"

    def resource_type(item: dict) -> str:
        res = item.get("baseResource") or item.get("resource") or {}
        return res.get("resourceType") or res.get("resourceDiscriminator") or res.get("type") or "?"

    roles = Counter((i.get("role") or {}).get("name") for i in items)
    return (f"item keys {sorted(items[0])}; resource types {dict(Counter(map(resource_type, items)))}; "
            f"role names in result {dict(roles)}")


def _ids(snap: Snapshot, sql: str, n: int = 8, spread: bool = False) -> list[str]:
    """``spread`` orders by a hash so the sample is not just the lowest ids (those can be special)."""
    order = "hash(id)" if spread else "id"
    return [r[0] for r in snap.sql(f"SELECT DISTINCT id FROM ({sql}) ORDER BY {order} LIMIT {n}").fetchall()]


def live_report(client: CollibraClient, snap: Snapshot) -> str:
    out = ["## live vs export: totals"]
    snap_counts = {
        "communities": snap.sql("SELECT count(DISTINCT community_id) FROM community").fetchone()[0],
        "domains": snap.sql("SELECT count(DISTINCT domain_id) FROM domain").fetchone()[0],
        "assets": snap.sql("SELECT count(DISTINCT asset_id) FROM asset").fetchone()[0],
    }
    totals = {k: _total(client, f"/{k}") for k in snap_counts}
    out += [f"{k}: live {totals[k]} | export {snap_counts[k]}" for k in snap_counts]
    out.append("probe: same totals with excludeMeta=false (parameter name unverified; unchanged numbers mean it was ignored)")
    with_meta: dict[str, int] = {}
    for k in snap_counts:
        try:
            with_meta[k] = _total(client, f"/{k}", excludeMeta="false")
            out.append(f"{k}: {with_meta[k]}")
        except CollibraHTTPError as exc:
            out.append(f"{k}: HTTP {exc.status_code}")
    if len(with_meta) == len(snap_counts):
        out.append("derived (assumes the export is a subset of live-with-meta):")
        for k in snap_counts:
            out.append(f"{k}: hidden by default {with_meta[k] - totals[k]} | "
                       f"in live-with-meta but not in export {with_meta[k] - snap_counts[k]}")

    samples = {
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
    domain_types = dict(snap.sql("SELECT domain_id, domain_type_name FROM domain").fetchall())
    roles = snap.sql(f"SELECT role_name, any_value(role_id) FROM ({_UNRESOLVED}) GROUP BY 1 ORDER BY 1").fetchall()
    out.append("\n## live lookup: what unresolved responsibility ids are (15 ids per role, spread sample)")
    for role, role_id in roles:
        safe = role.replace("'", "''")
        ids = _ids(snap, f"SELECT asset_id AS id FROM ({_UNRESOLVED}) WHERE role_name = '{safe}'", 15, spread=True)
        tally = Counter(resolve_id(client, i, domain_types) for i in ids)
        out.append(f"{role}: {dict(tally)}")
        out.append(f"  responsibilities API for this role: {probe_role(client, role_id)}")
    for title, ids in samples.items():
        out.append(f"\n## live lookup: {title} (sample of {len(ids)})")
        out += [f"{i[:8]}… -> {resolve_id(client, i)}" for i in ids] or ["(none)"]

    out.append("\n## live vs export: types where the EXPORT has more assets than the live list "
               "(live counts include subtypes, so only this direction is meaningful)")
    live_types = list(client.paginate("/assetTypes", page_size=1000))
    snap_by_type = dict(snap.sql("SELECT asset_type_name, count(*) FROM asset GROUP BY 1").fetchall())
    rows, same_as_global = [], 0
    for t in live_types:
        live = _total(client, "/assets", typeIds=[t["id"]])
        if live and live == totals["assets"]:
            same_as_global += 1
        exp = snap_by_type.get(t["name"], 0)
        if (live or 0) < exp:
            rows.append((t["name"], live, exp))
    if same_as_global >= 3:
        out.append("WARNING: the typeIds filter seems to be ignored (many types report the global total); "
                   "the per-type table below is NOT reliable.")
    rows.sort(key=lambda r: r[2] - (r[1] or 0), reverse=True)
    out.append("type | live | export")
    out.append(f"sum of excess in export: {sum(b - (a or 0) for _, a, b in rows)} (export assets {snap_counts['assets']} vs live {totals['assets']})")
    out += [f"{n} | {a} | {b}" for n, a, b in rows[:40]] or ["(none)"]
    return "\n".join(out)

"""Comparison of an export with the REST API of the same instance.

Needs a ``Snapshot`` and a ``CollibraClient``. Prints aggregates, ids and type names only.
"""

from __future__ import annotations

from collections import Counter

from ...client import CollibraClient, CollibraHTTPError, CollibraNotFound
from ..store import Snapshot
from .offline import UNRESOLVED



def _total(client: CollibraClient, path: str, **params) -> int | None:
    return client.get_json(path, {"limit": 1, "countLimit": -1, **params}).get("total")


def lookup_id(client: CollibraClient, id_: str) -> dict:
    """Ask the live API what an id is: {'kind', 'type', 'domain_id'} (no names), or kind None."""
    for kind, path in (("asset", "/assets/"), ("domain", "/domains/"), ("community", "/communities/")):
        try:
            obj = client.get_json(path + id_)
        except CollibraNotFound:
            continue
        except CollibraHTTPError as exc:
            return {"kind": kind, "error": exc.status_code}
        domain_id = (obj.get("domain") or {}).get("id") if kind == "asset" else None
        return {"kind": kind, "type": (obj.get("type") or {}).get("name"), "domain_id": domain_id}
    return {"kind": None}


def describe(info: dict, domain_types: dict[str, str] | None = None) -> str:
    """Format a ``lookup_id`` result. ``domain_types`` maps exported domain ids to type names."""
    if info["kind"] is None:
        return "not found as asset, domain or community"
    if "error" in info:
        return f"{info['kind']}? HTTP {info['error']}"
    label = info["kind"] + (f" (type {info['type']})" if info.get("type") else "")
    if info["kind"] == "asset" and domain_types is not None and info.get("domain_id"):
        dom = info["domain_id"]
        label += f" in {domain_types[dom]} domain" if dom in domain_types else " in a domain not in the export"
    return label


def resolve_id(client: CollibraClient, id_: str, domain_types: dict[str, str] | None = None) -> str:
    return describe(lookup_id(client, id_), domain_types)


def role_resources(client: CollibraClient, role_id: str) -> dict:
    """Ask the responsibilities API where a role is assigned: resource types and ids.

    Field names are tolerant on purpose; ``keys`` shows what the API really returned.
    """
    try:
        page = client.get_json("/responsibilities", {"roleIds": [role_id], "limit": 100})
    except CollibraHTTPError as exc:
        return {"error": exc.status_code}
    items = page.get("results", [])
    resources = []
    for item in items:
        res = item.get("baseResource") or item.get("resource") or {}
        rtype = res.get("resourceType") or res.get("resourceDiscriminator") or res.get("type") or "?"
        resources.append((rtype, res.get("id")))
    return {
        "keys": sorted(items[0]) if items else [],
        "resources": resources,
        "role_names": Counter((i.get("role") or {}).get("name") for i in items),
        "total": page.get("total"),
        "complete": len(items) < 100,
    }


def probe_role(client: CollibraClient, role_id: str) -> str:
    d = role_resources(client, role_id)
    if "error" in d:
        return f"HTTP {d['error']}"
    if not d["resources"]:
        return "no results"
    types = dict(Counter(r[0] for r in d["resources"]))
    return f"item keys {d['keys']}; resource types {types}; role names in result {dict(d['role_names'])}"


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
    roles = snap.sql(f"SELECT role_name, any_value(role_id) FROM ({UNRESOLVED}) GROUP BY 1 ORDER BY 1").fetchall()
    out.append("\n## live lookup: what unresolved responsibility ids are (15 ids per role, spread sample)")
    for role, role_id in roles:
        safe = role.replace("'", "''")
        ids = _ids(snap, f"SELECT asset_id AS id FROM ({UNRESOLVED}) WHERE role_name = '{safe}'", 15, spread=True)
        infos = [lookup_id(client, i) for i in ids]
        out.append(f"{role}: {dict(Counter(describe(i, domain_types) for i in infos))}")
        out.append(f"  responsibilities API for this role: {probe_role(client, role_id)}")
        detail = role_resources(client, role_id)
        if "error" not in detail:
            assigned = {rid for rtype, rid in detail["resources"] if rtype == "Domain" and rid}
            sampled = {i["domain_id"] for i in infos if i.get("domain_id")}
            if sampled:
                inside = len(sampled & assigned)
                out.append(
                    f"  domain-level expansion test: {inside} of {len(sampled)} distinct domains holding the sampled assets "
                    f"are domains this role is assigned on directly ({'API list complete' if detail['complete'] else 'API list truncated'}); "
                    f"role has {len(assigned)} domain-level assignments in the API")
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

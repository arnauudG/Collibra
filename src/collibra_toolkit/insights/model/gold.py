"""Gold tables: reporting-ready aggregates built on the model (silver).

Everything client-specific (which attribute is "the definition", which role is "owner") lives in
``GoldConfig``, never in the SQL. Gold tables hold **additive counts**, not ratios: compute a
percentage in the BI tool as ``sum(with_definition) / sum(assets)`` so any slicing stays correct.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..store import Snapshot
from .views import build_model


@dataclass(frozen=True)
class GoldConfig:
    governed_types: tuple[str, ...] = ("Business Term",)   # asset types the scorecard is about
    definition_attribute: str = "Definition"               # attribute type that holds the definition
    owner_roles: tuple[str, ...] = ("Owner",)              # resource roles that count as "owned"
    approved_statuses: tuple[str, ...] = ("Approved",)     # statuses that count as "approved"
    stale_days: int = 365                                  # not edited for this long = stale
    include_usernames: bool = False                        # usernames are personal data: off by default


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _in(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(_quote(v) for v in values) + ")" if values else "(NULL)"


def _products(c: GoldConfig) -> list[tuple[str, str]]:
    stale = f"CASE WHEN a.edited_date < a.snapshot_date - INTERVAL {int(c.stale_days)} DAY THEN 1 ELSE 0 END"
    name_col = "u.username," if c.include_usernames else ""
    name_grp = ", u.username" if c.include_usernames else ""
    return [
        ("gold_catalog_inventory", f"""
            SELECT a.snapshot_date, a.community_name, a.domain_name, a.domain_type_name,
                   a.asset_type_name, a.status_name,
                   count(*) AS assets,
                   sum({stale}) AS stale_assets
            FROM dim_asset a
            GROUP BY 1, 2, 3, 4, 5, 6"""),
        ("gold_governance_scorecard", f"""
            WITH defined AS (
                SELECT DISTINCT snapshot_date, asset_id FROM fact_attribute
                WHERE attribute_type_name = {_quote(c.definition_attribute)} AND coalesce(value_as_text, '') <> ''),
            owned AS (
                SELECT DISTINCT snapshot_date, asset_id FROM fact_responsibility
                WHERE role_name IN {_in(c.owner_roles)} AND asset_resolution = 'in_export'),
            connected AS (
                SELECT snapshot_date, asset_id1 AS asset_id FROM fact_relation
                UNION
                SELECT snapshot_date, asset_id2 FROM fact_relation)
            SELECT a.snapshot_date, a.community_name, a.domain_name, a.asset_type_name,
                   count(*) AS assets,
                   count(d.asset_id) AS with_definition,
                   count(o.asset_id) AS with_owner,
                   count(k.asset_id) AS connected,
                   sum(CASE WHEN a.status_name IN {_in(c.approved_statuses)} THEN 1 ELSE 0 END) AS approved,
                   sum({stale}) AS stale
            FROM dim_asset a
            LEFT JOIN defined d ON d.snapshot_date = a.snapshot_date AND d.asset_id = a.asset_id
            LEFT JOIN owned o ON o.snapshot_date = a.snapshot_date AND o.asset_id = a.asset_id
            LEFT JOIN connected k ON k.snapshot_date = a.snapshot_date AND k.asset_id = a.asset_id
            WHERE a.asset_type_name IN {_in(c.governed_types)}
            GROUP BY 1, 2, 3, 4"""),
        ("gold_stewardship_workload", f"""
            SELECT r.snapshot_date, r.role_name, r.user_id, {name_col}
                   count(DISTINCT r.asset_id) AS assets,
                   count(DISTINCT a.domain_id) AS domains
            FROM fact_responsibility r
            JOIN dim_user u ON u.snapshot_date = r.snapshot_date AND u.user_id = r.user_id
            JOIN dim_asset a ON a.snapshot_date = r.snapshot_date AND a.asset_id = r.asset_id
            WHERE r.asset_resolution = 'in_export'
            GROUP BY r.snapshot_date, r.role_name, r.user_id{name_grp}"""),
        ("gold_asset_connectivity", """
            WITH ends AS (
                SELECT snapshot_date, asset_id1 AS asset_id FROM fact_relation
                UNION ALL
                SELECT snapshot_date, asset_id2 FROM fact_relation),
            degree AS (SELECT snapshot_date, asset_id, count(*) AS relations FROM ends GROUP BY 1, 2)
            SELECT a.snapshot_date, a.asset_type_name,
                   count(*) AS assets,
                   count(g.asset_id) AS connected_assets,
                   coalesce(sum(g.relations), 0) AS relation_endpoints
            FROM dim_asset a
            LEFT JOIN degree g ON g.snapshot_date = a.snapshot_date AND g.asset_id = a.asset_id
            GROUP BY 1, 2"""),
    ]


def build_gold(snap: Snapshot, config: GoldConfig | None = None) -> list[str]:
    """Create the gold views (building the model first); returns their names.

    ``gold_usage_daily`` is added only when the optional ``view_events`` table exists.
    """
    config = config or GoldConfig()
    build_model(snap, include_pii=False)
    products = _products(config)
    if "view_events" in snap.tables:
        products.append(("gold_usage_daily", """
            SELECT snapshot_date, count(DISTINCT user_id) AS active_users, count(*) AS views
            FROM fact_view_event GROUP BY 1"""))
    for name, sql in products:
        snap.con.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")
    return [name for name, _ in products]

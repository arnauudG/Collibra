"""Live diagnostics: the export compared with the REST API (fake client)."""

from collibra_toolkit import CollibraNotFound
from collibra_toolkit.insights.diagnostics import live_report, lookup_id, probe_role, resolve_id, role_resources, snapshot_report


class FakeLive:
    """Duck-typed CollibraClient: routes map path -> value or exception."""

    def __init__(self, routes, types=()):
        self.routes, self.types, self.calls = routes, list(types), []

    def get_json(self, path, params=None):
        self.calls.append((path, params))
        r = self.routes.get(path, CollibraNotFound(404, ""))
        if isinstance(r, Exception):
            raise r
        return r(params) if callable(r) else r

    def paginate(self, path, params=None, page_size=1000):
        return iter(self.types)


def test_resolve_id():
    c = FakeLive({"/domains/d1": {"type": {"name": "Glossary"}}, "/communities/c1": {}, "/assets/bad": CollibraNotFound(404, "")})
    assert resolve_id(c, "d1") == "domain (type Glossary)"
    assert resolve_id(c, "c1") == "community"
    assert resolve_id(c, "zzz") == "not found as asset, domain or community"


def test_live_report_flags_differences(snap):  # noqa: F811
    totals = {"/communities": {"total": 1}, "/domains": {"total": 1}, "/assets": lambda p: {"total": 9 if "typeIds" not in p else (1 if p["typeIds"] == ["t-term"] else 0)}}
    c = FakeLive(totals, types=[{"id": "t-term", "name": "Term"}, {"id": "t-x", "name": "Hidden Type"}])
    text = live_report(c, snap)
    assert "assets: live 9 | export 2" in text
    assert "Term | 1 | 2" in text and "Hidden Type" not in text   # only types where export > live
    assert "sum of excess in export: 1" in text
    assert "excludeMeta=false" in text and "id shape" not in text
    assert "not found as asset, domain or community" in text      # orphan domain id 'gone'
    assert "derived (assumes" in text
    assert "WARNING" not in text


def test_live_report_warns_when_type_filter_ignored(snap):  # noqa: F811
    c = FakeLive({"/communities": {"total": 1}, "/domains": {"total": 1}, "/assets": {"total": 9}},
                 types=[{"id": f"t{i}", "name": f"T{i}"} for i in range(4)])
    assert "WARNING" in live_report(c, snap)


def test_resolve_id_reports_the_domain_kind_of_an_asset():
    c = FakeLive({"/assets/x": {"type": {"name": "Assignment Characteristics"}, "domain": {"id": "d9"}},
                  "/assets/y": {"type": {"name": "T"}, "domain": {"id": "unknown"}}})
    types = {"d9": "Issues Vocabulary Type"}
    assert resolve_id(c, "x", types) == "asset (type Assignment Characteristics) in Issues Vocabulary Type domain"
    assert resolve_id(c, "y", types) == "asset (type T) in a domain not in the export"
    assert resolve_id(c, "x") == "asset (type Assignment Characteristics)"      # no domain context asked for


def test_probe_role_reports_resource_types_and_keys():
    items = [{"role": {"name": "Data Quality Manager"}, "baseResource": {"resourceType": "DataQualityJob"}}] * 3
    c = FakeLive({"/responsibilities": {"results": items}})
    out = probe_role(c, "role-id")
    assert "DataQualityJob" in out and "3" in out and "baseResource" in out
    assert c.calls[0][1]["roleIds"] == ["role-id"]
    assert probe_role(FakeLive({"/responsibilities": {"results": []}}), "r") == "no results"


def test_role_resources_collects_types_and_ids():
    items = [
        {"role": {"name": "R"}, "baseResource": {"resourceType": "Domain", "id": "d1"}},
        {"role": {"name": "R"}, "baseResource": {"resourceType": "Community", "id": "c1"}},
    ]
    d = role_resources(FakeLive({"/responsibilities": {"results": items, "total": 2}}), "role")
    assert d["resources"] == [("Domain", "d1"), ("Community", "c1")] and d["complete"] and d["total"] == 2
    assert role_resources(FakeLive({"/responsibilities": CollibraNotFound(404, "")}), "r") == {"error": 404}


def test_lookup_id_is_structured():
    c = FakeLive({"/assets/a": {"type": {"name": "T"}, "domain": {"id": "d1"}}})
    assert lookup_id(c, "a") == {"kind": "asset", "type": "T", "domain_id": "d1"}
    assert lookup_id(c, "zzz") == {"kind": None}


def test_live_report_tests_the_domain_expansion_hypothesis(tmp_path):
    """A role whose unresolved asset rows live in domains the role is assigned on directly."""
    import datetime as dt

    import pyarrow as pa
    import pyarrow.parquet as pq

    from collibra_toolkit.insights.store import Snapshot

    day = dt.date(2026, 10, 10)
    cols = {
        "responsibility": [dict(role_id="r1", role_name="Community Manager", asset_id=f"hidden{i}", user_id="u1", group_id=None)
                           for i in range(3)],
        "asset": [dict(asset_id="a1", domain_id="d1", asset_type_name="T")],
        "domain": [dict(domain_id="d1", domain_type_name="Glossary", is_domain_system=False, community_id="c1")],
        "community": [dict(community_id="c1")],
    }
    for name, rows in cols.items():
        d = tmp_path / name / "snapshot_date_year=2026" / "snapshot_date_month=10" / "snapshot_date_day=10"
        d.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist([{"snapshot_date": day, **r} for r in rows]), d / "p.parquet")
    snap = Snapshot(tmp_path)
    routes = {
        "/communities": {"total": 1}, "/domains": {"total": 1}, "/assets": {"total": 4},
        **{f"/assets/hidden{i}": {"type": {"name": "Assignment Characteristics"}, "domain": {"id": "hd"}} for i in range(3)},
        "/responsibilities": {"results": [{"role": {"name": "Community Manager"},
                                           "baseResource": {"resourceType": "Domain", "id": "hd"}}]},
    }
    text = live_report(FakeLive(routes), snap)
    assert "asset (type Assignment Characteristics) in a domain not in the export': 3" in text
    assert "domain-level expansion test: 1 of 1 distinct domains" in text
    assert "API list complete" in text

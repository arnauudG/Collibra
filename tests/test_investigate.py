from test_model import snap  # noqa: F401  (fixture: synthetic rows, real column names)

from collibra_insights import CollibraNotFound
from collibra_insights.investigate import live_report, resolve_id, snapshot_report


def test_snapshot_report_sections(snap, tmp_path):  # noqa: F811
    text = snapshot_report(snap)
    for title in ("file layout", "attribute kind", "community.level", "responsibilities: overview", "shape of the ids", "is_system flags",
                  "unresolved responsibility ids", "assets whose domain is missing"):
        assert title in text
    assert ".parquet" in text
    assert "STRING | 1 | 1 | 0 | 0 | 0" in text            # STRING fills only the text column
    assert "NUMERIC | 1 | 0 | 1 | 0 | 0" in text
    assert "Term | 1 | 1" in text                          # the one orphan asset, by type
    assert "(no rows)" in text                              # no Issue content in the fixture
    assert "SECRET" not in text and "j@x.com" not in text   # no row content / PII


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
    assert "WARNING" not in text


def test_live_report_warns_when_type_filter_ignored(snap):  # noqa: F811
    c = FakeLive({"/communities": {"total": 1}, "/domains": {"total": 1}, "/assets": {"total": 9}},
                 types=[{"id": f"t{i}", "name": f"T{i}"} for i in range(4)])
    assert "WARNING" in live_report(c, snap)

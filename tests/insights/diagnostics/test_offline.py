"""Offline diagnostics: aggregate evidence from a snapshot alone."""

from collibra_toolkit import CollibraNotFound
from collibra_toolkit.insights.diagnostics import live_report, lookup_id, probe_role, resolve_id, role_resources, snapshot_report


def test_snapshot_report_sections(snap, tmp_path):  # noqa: F811
    text = snapshot_report(snap)
    for title in ("file layout", "attribute kind", "community.level", "responsibilities: overview", "shape of the ids", "is_system flags", "domains with / without assets",
                  "unresolved responsibility ids", "assets whose domain is missing"):
        assert title in text
    assert ".parquet" in text
    assert "STRING | 1 | 1 | 0 | 0 | 0" in text            # STRING fills only the text column
    assert "NUMERIC | 1 | 0 | 1 | 0 | 0" in text
    assert "Term | 1 | 1" in text                          # the one orphan asset, by type
    assert "(no rows)" in text                              # no Issue content in the fixture
    assert "SECRET" not in text and "j@x.com" not in text   # no row content / PII

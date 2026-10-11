import datetime as dt

import pytest
from fakes import FakeResp, FakeSession, zip_bytes

from collibra_toolkit import CollibraClient, CollibraError, CollibraNotFound
from collibra_toolkit.insights import InsightsClient
from collibra_toolkit.insights.client import retention_note, validate_snapshot_date

TODAY = dt.date(2026, 10, 11)


def insights(*responses):
    sess = FakeSession(*responses)
    return InsightsClient(CollibraClient("https://x.collibra.com", token="t", session=sess)), sess


def test_date_validation():
    assert validate_snapshot_date("2026-10-01", TODAY) == dt.date(2026, 10, 1)
    for bad in ("2026-10-12", "10/01/2026"):
        with pytest.raises(CollibraError):
            validate_snapshot_date(bad, TODAY)


def test_retention_is_a_warning_not_an_error():
    assert retention_note(dt.date(2026, 10, 1), TODAY) is None  # last 31 days
    assert retention_note(dt.date(2026, 6, 30), TODAY) is None  # month-end within 12 months
    assert retention_note(dt.date(2024, 12, 31), TODAY) is None  # year-end, any age
    assert retention_note(dt.date(2026, 6, 29), TODAY)  # ordinary old day
    assert retention_note(dt.date(2024, 6, 30), TODAY)  # month-end older than 12 months
    with pytest.warns(UserWarning):
        validate_snapshot_date("2026-06-29", TODAY)


def test_download_extracts_and_calls_endpoint(tmp_path):
    day = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    ic, sess = insights(FakeResp(200, zip_bytes({"asset/part.parquet": b"x"})))
    out = ic.download_snapshot(day, tmp_path)
    assert (out / "asset" / "part.parquet").exists()
    method, url, kw = sess.calls[0]
    assert (method, url) == ("GET", "https://x.collibra.com/rest/2.0/reporting/insights/directDownload")
    assert kw["params"] == {"snapshotDate": day, "format": "zip"} and kw["allow_redirects"] and kw["stream"]


def test_download_closes_response_and_explains_404(tmp_path):
    day = dt.date.today().isoformat()
    resp = FakeResp(200, zip_bytes({"a/b.parquet": b"x"}))
    insights(resp)[0].download_snapshot(day, tmp_path)
    assert resp.closed
    with pytest.raises(CollibraNotFound, match="not generated yet"):
        insights(FakeResp(404, b""))[0].download_snapshot(day, tmp_path)


def test_download_rejects_zip_slip(tmp_path):
    day = dt.date.today().isoformat()
    with pytest.raises(CollibraError, match="unsafe"):
        insights(FakeResp(200, zip_bytes({"../evil.txt": b"x"})))[0].download_snapshot(day, tmp_path)
    assert not (tmp_path.parent / "evil.txt").exists()


def test_download_is_atomic_and_clean(tmp_path):
    day = dt.date.today().isoformat()
    stale = tmp_path / f"insights-{day}" / "asset"
    stale.mkdir(parents=True)
    (stale / "old.parquet").write_bytes(b"stale")
    out = insights(FakeResp(200, zip_bytes({"asset/new.parquet": b"x"})))[0].download_snapshot(day, tmp_path)
    assert (out / "asset" / "new.parquet").exists() and not (out / "asset" / "old.parquet").exists()

    with pytest.raises(CollibraError, match="valid ZIP"):
        insights(FakeResp(200, b"not a zip"))[0].download_snapshot(day, tmp_path)
    assert (out / "asset" / "new.parquet").exists()  # earlier good extraction survives
    assert not list(tmp_path.glob("*.zip")) and not list(tmp_path.glob("*.part"))
    assert not list(tmp_path.glob(".insights-*"))


def test_legacy_endpoint_and_unknown_endpoint(tmp_path):
    day = dt.date.today().isoformat()
    ic, sess = insights(FakeResp(200, zip_bytes({"asset/x.parquet": b"x"})))
    ic.download_snapshot(day, tmp_path, endpoint="legacy")
    assert sess.calls[0][1].endswith("/rest/2.0/reporting/insights/download")
    with pytest.raises(CollibraError, match="endpoint"):
        ic.download_snapshot(day, tmp_path, endpoint="nope")


def test_list_tables_reads_the_zip_without_extracting(tmp_path):
    day = dt.date.today().isoformat()
    part = "snapshot_date_year=2026/snapshot_date_month=10/snapshot_date_day=10/p.parquet"
    z = zip_bytes({f"wrapper/asset/{part}": b"x", f"wrapper/view_events/{part}": b"x", "wrapper/notes.txt": b"hi"})
    assert insights(FakeResp(200, z))[0].list_tables(day) == ["asset", "view_events"]
    flat = zip_bytes({"asset/p.parquet": b"x", "domain/p.parquet": b"x"})
    assert insights(FakeResp(200, flat))[0].list_tables(day) == ["asset", "domain"]
    with pytest.raises(CollibraError, match="valid ZIP"):
        insights(FakeResp(200, b"not a zip"))[0].list_tables(day)

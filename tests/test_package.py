import datetime as dt
import io
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from collibra_insights import CollibraClient, CollibraError, Snapshot
from collibra_insights.client import retention_note, validate_snapshot_date

TODAY = dt.date(2026, 10, 11)


def test_date_validation():
    assert validate_snapshot_date("2026-10-01", TODAY) == dt.date(2026, 10, 1)
    for bad in ("2026-10-12", "10/01/2026"):
        with pytest.raises(CollibraError):
            validate_snapshot_date(bad, TODAY)


def test_retention_is_a_warning_not_an_error():
    assert retention_note(dt.date(2026, 10, 1), TODAY) is None       # last 31 days
    assert retention_note(dt.date(2026, 6, 30), TODAY) is None       # month-end within 12 months
    assert retention_note(dt.date(2024, 12, 31), TODAY) is None      # year-end, any age
    assert retention_note(dt.date(2026, 6, 29), TODAY)               # ordinary old day
    assert retention_note(dt.date(2024, 6, 30), TODAY)               # month-end older than 12 months
    with pytest.warns(UserWarning):
        validate_snapshot_date("2026-06-29", TODAY)


def _make_snapshot(root):
    # SYNTHETIC columns, only to exercise the code; not Collibra's real schema.
    for name in ("asset", "domain", "mystery_table"):
        d = root / name
        d.mkdir(parents=True)
        pq.write_table(pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]}), d / "part-0.parquet")


def test_snapshot_discovers_tables(tmp_path):
    _make_snapshot(tmp_path)
    s = Snapshot(tmp_path)
    assert s.tables == ["asset", "domain", "mystery_table"]
    assert s.undocumented() == ["mystery_table"]
    assert "community" in s.missing()
    assert s.row_counts()["asset"] == 3
    assert [c[0] for c in s.describe("asset")] == ["id", "name"]
    assert "asset" in s.report()


def test_snapshot_hive_partitioned_layout(tmp_path):
    """Real snapshots: <table>/snapshot_date_year=Y/snapshot_date_month=M/snapshot_date_day=D/file.parquet"""
    for name, n in (("asset", 3), ("responsibility", 2)):
        d = tmp_path / "wrapper" / name / "snapshot_date_year=2026" / "snapshot_date_month=10" / "snapshot_date_day=10"
        d.mkdir(parents=True)
        pq.write_table(pa.table({"id": list(range(n))}), d / "part-0.parquet")
    s = Snapshot(tmp_path)
    assert s.tables == ["asset", "responsibility"]
    assert s.row_counts() == {"asset": 3, "responsibility": 2}
    assert "snapshot_date_day" in [c[0] for c in s.describe("asset")]


def test_cli_query(tmp_path, capsys):
    from collibra_insights.cli import main

    _make_snapshot(tmp_path)
    main(["query", str(tmp_path), "select count(*) as n from asset"])
    assert capsys.readouterr().out.splitlines() == ["n", "3"]


def test_snapshot_empty_dir_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        Snapshot(tmp_path)


class FakeResp:
    def __init__(self, status, content=b""):
        self.status_code, self._c, self.text = status, content, content.decode("latin1")

    def iter_content(self, n):
        yield self._c


class FakeSession:
    def __init__(self, resp):
        self.resp, self.headers, self.auth, self.calls = resp, {}, None, []

    def get(self, url, **kw):
        self.calls.append((url, kw))
        return self.resp


def _zip_bytes(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, b in members.items():
            z.writestr(n, b)
    return buf.getvalue()


def test_download_extracts_and_calls_endpoint(tmp_path):
    day = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    sess = FakeSession(FakeResp(200, _zip_bytes({"asset/part.parquet": b"x"})))
    c = CollibraClient("https://x.collibra.com/", username="u", password="p", session=sess)
    out = c.download_snapshot(day, tmp_path)
    assert (out / "asset" / "part.parquet").exists()
    url, kw = sess.calls[0]
    assert url == "https://x.collibra.com/rest/2.0/reporting/insights/directDownload"
    assert kw["params"] == {"snapshotDate": day, "format": "zip"} and kw["allow_redirects"]


def test_download_rejects_zip_slip_and_http_errors(tmp_path):
    day = dt.date.today().isoformat()
    evil = FakeSession(FakeResp(200, _zip_bytes({"../evil.txt": b"x"})))
    with pytest.raises(CollibraError, match="unsafe"):
        CollibraClient("https://x", token="t", session=evil).download_snapshot(day, tmp_path)
    with pytest.raises(CollibraError, match="HTTP 403"):
        CollibraClient("https://x", token="t", session=FakeSession(FakeResp(403, b"no"))).download_snapshot(day, tmp_path)


def test_requires_credentials():
    with pytest.raises(CollibraError):
        CollibraClient("https://x")


def test_download_is_atomic_and_clean(tmp_path):
    day = dt.date.today().isoformat()
    ok = FakeSession(FakeResp(200, _zip_bytes({"asset/new.parquet": b"x"})))
    c = CollibraClient("https://x", token="t", session=ok)
    stale = tmp_path / f"insights-{day}" / "asset"
    stale.mkdir(parents=True)
    (stale / "old.parquet").write_bytes(b"stale")
    out = c.download_snapshot(day, tmp_path)
    assert (out / "asset" / "new.parquet").exists() and not (out / "asset" / "old.parquet").exists()

    bad = CollibraClient("https://x", token="t", session=FakeSession(FakeResp(200, b"not a zip")))
    with pytest.raises(CollibraError, match="valid ZIP"):
        bad.download_snapshot(day, tmp_path)
    assert (out / "asset" / "new.parquet").exists()                  # earlier good extraction survives
    assert not list(tmp_path.glob("*.zip")) and not list(tmp_path.glob("*.part")) and not list(tmp_path.glob(".insights-*"))

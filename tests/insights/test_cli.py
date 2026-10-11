"""The Insights CLI (composition root)."""

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from tests.insights.helpers import make_flat_snapshot


def test_cli_query_from_file(tmp_path, capsys):
    from collibra_toolkit.insights.cli import main

    make_flat_snapshot(tmp_path)
    q = tmp_path / "q.sql"
    q.write_text("select count(*) as n\nfrom asset\n")
    main(["query", str(tmp_path), "--file", str(q)])
    assert capsys.readouterr().out.splitlines() == ["n", "3"]


def test_cli_query(tmp_path, capsys):
    from collibra_toolkit.insights.cli import main

    make_flat_snapshot(tmp_path)
    main(["query", str(tmp_path), "select count(*) as n from asset"])
    assert capsys.readouterr().out.splitlines() == ["n", "3"]


def test_cli_reports_errors_in_one_line(monkeypatch):
    from collibra_toolkit.insights.cli import main

    monkeypatch.delenv("COLLIBRA_URL", raising=False)
    with pytest.raises(SystemExit) as info:
        main(["ping"])
    assert "COLLIBRA_URL is not set" in str(info.value)

"""The generic CLI: ping, and initiatives discovered through entry points, never imported by name."""

import pytest

from collibra_toolkit import CollibraClient
from collibra_toolkit.cli import INITIATIVES_GROUP, initiatives, main
from tests.insights.helpers import make_flat_snapshot
from tests.support.fakes import FakeResp, make_client


def test_ping_prints_the_auth_method_and_errors_are_one_line(monkeypatch, capsys):
    items = [{"id": f"id{i}"} for i in range(5)]
    pages = [FakeResp(payload={"results": items[i:i + 2], "total": 5, "limit": 2}) for i in (0, 0, 2, 4)]
    client, _ = make_client(*pages)
    monkeypatch.setattr(CollibraClient, "from_env", classmethod(lambda cls, *a, **k: client))
    main(["ping"])
    out = capsys.readouterr().out
    assert "reachable: yes" in out and "auth method actually used: basic" in out

    denied, _ = make_client(FakeResp(401, b"nope"))
    monkeypatch.setattr(CollibraClient, "from_env", classmethod(lambda cls, *a, **k: denied))
    with pytest.raises(SystemExit) as info:
        main(["ping"])
    assert "HTTP 401" in str(info.value) and "COLLIBRA_CLIENT_ID" in str(info.value)


def test_an_initiative_is_dispatched_by_name_without_the_cli_knowing_it(monkeypatch):
    seen = []
    monkeypatch.setattr("collibra_toolkit.cli.initiatives", lambda: {"demo": lambda: (lambda argv: seen.append(argv))})
    main(["demo", "--flag", "x"])
    assert seen == [["--flag", "x"]]


def test_help_lists_whatever_is_installed(monkeypatch, capsys):
    monkeypatch.setattr("collibra_toolkit.cli.initiatives", lambda: {"demo": lambda: None})
    with pytest.raises(SystemExit) as info:
        main(["-h"])
    assert info.value.code == 0
    assert "demo" in capsys.readouterr().out


def test_insights_registers_itself_through_an_entry_point(tmp_path, capsys):
    assert INITIATIVES_GROUP == "collibra_toolkit.initiatives"
    registry = initiatives()
    assert "insights" in registry
    make_flat_snapshot(tmp_path)
    main(["insights", "query", str(tmp_path), "select count(*) as n from asset"])
    assert capsys.readouterr().out.splitlines() == ["n", "3"]

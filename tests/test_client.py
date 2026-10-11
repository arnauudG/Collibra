import pytest
import requests
from fakes import FakeResp, FakeSession

from collibra_toolkit import (
    CollibraAuthError,
    CollibraClient,
    CollibraError,
    CollibraHTTPError,
    CollibraNotFound,
)


def make(*responses, **kw):
    sess = FakeSession(*responses, **kw)
    return CollibraClient("https://x.collibra.com/", username="u", password="p", session=sess), sess


def test_requires_credentials():
    with pytest.raises(CollibraError):
        CollibraClient("https://x")


def test_auth_modes():
    s = FakeSession(FakeResp())
    CollibraClient("https://x", token="t", session=s)
    assert s.headers["Authorization"] == "Bearer t"
    s = FakeSession(FakeResp())
    CollibraClient("https://x", username="u", password="p", session=s)
    assert s.auth == ("u", "p")


def test_from_env():
    env = {"COLLIBRA_URL": "https://x", "COLLIBRA_TOKEN": "t"}
    assert CollibraClient.from_env(env, session=FakeSession(FakeResp())).base_url == "https://x"
    with pytest.raises(CollibraError, match="COLLIBRA_URL"):
        CollibraClient.from_env({})


def test_url_building_and_default_options():
    c, sess = make(FakeResp(payload={"ok": 1}))
    assert c.get_json("/communities", {"limit": 2}) == {"ok": 1}
    method, url, kw = sess.calls[0]
    assert (method, url) == ("GET", "https://x.collibra.com/rest/2.0/communities")
    assert kw["params"] == {"limit": 2} and kw["allow_redirects"] and kw["timeout"] == 60


@pytest.mark.parametrize(
    "status,exc",
    [(401, CollibraAuthError), (403, CollibraAuthError), (404, CollibraNotFound), (500, CollibraHTTPError)],
)
def test_http_errors_are_typed(status, exc):
    c, _ = make(FakeResp(status, b"nope"))
    with pytest.raises(exc) as info:
        c.request("GET", "/x")
    assert info.value.status_code == status and "nope" in str(info.value)


def test_network_errors_do_not_leak_urls():
    c, _ = make(FakeResp(), raises=requests.ConnectionError("https://bucket/x?X-Amz-Signature=secret"))
    with pytest.raises(CollibraError) as info:
        c.request("GET", "/x")
    assert "secret" not in str(info.value) and "ConnectionError" in str(info.value)


def page(items, total=None, limit=2):
    return FakeResp(payload={"results": items, "total": total, "limit": limit})


def test_paginate_follows_offsets_until_total():
    c, sess = make(page([1, 2], total=5), page([3, 4], total=5), page([5], total=5))
    assert list(c.paginate("/things", page_size=2)) == [1, 2, 3, 4, 5]
    assert [call[2]["params"]["offset"] for call in sess.calls] == [0, 2, 4]


def test_paginate_without_total_stops_on_short_page():
    c, sess = make(page([1, 2]), page([3]))
    assert list(c.paginate("/things", page_size=2)) == [1, 2, 3]
    assert len(sess.calls) == 2


def test_paginate_respects_server_capped_limit():
    # asked for 1000, server answers 2 per page: a "short" page vs. our request must not stop early
    c, sess = make(page([1, 2], limit=2), page([3, 4], limit=2), page([], limit=2))
    assert list(c.paginate("/things", page_size=1000)) == [1, 2, 3, 4]


def test_paginate_empty():
    c, _ = make(page([], total=0))
    assert list(c.paginate("/things")) == []


def test_ping_reports_counts_only():
    from collibra_toolkit.health import ping

    items = [{"id": f"id{i}", "name": "SECRET"} for i in range(5)]
    first = FakeResp(payload={"results": items[:2], "total": 5, "limit": 2, "offset": 0})
    pages = [FakeResp(payload={"results": items[i:i + 2], "total": 5, "limit": 2}) for i in (0, 2, 4)]
    c, _ = make(first, *pages)
    out = ping(c)
    assert "total communities: 5" in out[2] and "got 5, unique ids 5" in out[3]
    assert "SECRET" not in "\n".join(out)


def test_toolkit_cli_ping_and_error_messages(monkeypatch, capsys):
    from collibra_toolkit.cli import main

    items = [{"id": f"id{i}"} for i in range(5)]
    pages = [FakeResp(payload={"results": items[i:i + 2], "total": 5, "limit": 2}) for i in (0, 0, 2, 4)]
    client, _ = make(*pages)
    monkeypatch.setattr(CollibraClient, "from_env", classmethod(lambda cls, *a, **k: client))
    main(["ping"])
    assert "reachable: yes" in capsys.readouterr().out

    denied, _ = make(FakeResp(401, b"nope"))
    monkeypatch.setattr(CollibraClient, "from_env", classmethod(lambda cls, *a, **k: denied))
    with pytest.raises(SystemExit) as info:
        main(["ping"])
    assert "HTTP 401" in str(info.value) and "COLLIBRA_USER" in str(info.value)


def test_toolkit_cli_delegates_to_initiatives(tmp_path, capsys):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from collibra_toolkit.cli import main

    d = tmp_path / "asset"
    d.mkdir()
    pq.write_table(pa.table({"id": [1, 2]}), d / "p.parquet")
    main(["insights", "query", str(tmp_path), "select count(*) as n from asset"])
    assert capsys.readouterr().out.splitlines() == ["n", "2"]

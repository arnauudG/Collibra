"""The generic connectivity check."""

import pytest
import requests

from collibra_toolkit import (
    CollibraAuthError,
    CollibraClient,
    CollibraError,
    CollibraHTTPError,
    CollibraNotFound,
    CollibraRateLimitError,
    CollibraServerError,
)
from tests.support.fakes import FakeResp, FakeSession, RoutedSession, make_client


def test_ping_reports_counts_only():
    from collibra_toolkit.client.health import ping

    items = [{"id": f"id{i}", "name": "SECRET"} for i in range(5)]
    first = FakeResp(payload={"results": items[:2], "total": 5, "limit": 2, "offset": 0})
    pages = [FakeResp(payload={"results": items[i:i + 2], "total": 5, "limit": 2}) for i in (0, 2, 4)]
    c, _ = make_client(first, *pages)
    out = ping(c)
    assert "total communities: 5" in out[2] and "got 5, unique ids 5" in out[3]
    assert "SECRET" not in "\n".join(out)

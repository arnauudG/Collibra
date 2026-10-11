"""Offset/limit pagination."""

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


def page(items, total=None, limit=2):
    return FakeResp(payload={"results": items, "total": total, "limit": limit})


def test_paginate_follows_offsets_until_total():
    c, sess = make_client(page([1, 2], total=5), page([3, 4], total=5), page([5], total=5))
    assert list(c.paginate("/things", page_size=2)) == [1, 2, 3, 4, 5]
    assert [call[2]["params"]["offset"] for call in sess.calls] == [0, 2, 4]


def test_paginate_without_total_stops_on_short_page():
    c, sess = make_client(page([1, 2]), page([3]))
    assert list(c.paginate("/things", page_size=2)) == [1, 2, 3]
    assert len(sess.calls) == 2


def test_paginate_respects_server_capped_limit():
    # asked for 1000, server answers 2 per page: a "short" page vs. our request must not stop early
    c, sess = make_client(page([1, 2], limit=2), page([3, 4], limit=2), page([], limit=2))
    assert list(c.paginate("/things", page_size=1000)) == [1, 2, 3, 4]


def test_paginate_empty():
    c, _ = make_client(page([], total=0))
    assert list(c.paginate("/things")) == []

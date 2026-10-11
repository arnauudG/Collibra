"""Offset/limit pagination over Collibra's ``{total, offset, limit, results}`` envelope."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any


def paginate(
    get_json: Callable[[str, Mapping[str, Any] | None], Any],
    path: str,
    params: Mapping[str, Any] | None = None,
    page_size: int = 1000,
) -> Iterator[Any]:
    """Yield the items of ``results`` across pages.

    Verified live on ``/communities`` (envelope keys and a multi-page walk as assumed); other
    endpoints are untested. Copes with servers that cap the page size.
    """
    offset = 0
    while True:
        page = get_json(path, {**(params or {}), "offset": offset, "limit": page_size})
        results = page.get("results", [])
        yield from results
        offset += len(results)
        limit = page.get("limit") or page_size
        total = page.get("total")
        if not results or (total and offset >= total) or (not total and len(results) < limit):
            return

"""Generic connectivity check, usable by any initiative."""

from __future__ import annotations

from itertools import islice

from .client import CollibraClient


def ping(client: CollibraClient) -> list[str]:
    """Live credentials + pagination check. Reports counts and key names only, no content."""
    page = client.get_json("/communities", {"limit": 2})
    items = list(islice(client.paginate("/communities", page_size=2), 5))
    ids = [i.get("id") for i in items]
    return [
        "reachable: yes",
        f"envelope keys: {sorted(page)}",
        f"total communities: {page.get('total')}",
        f"paginate(page_size=2), first 5 items: got {len(items)}, unique ids {len(set(ids))}",
        f"auth method actually used: {client.auth_method}",
    ]

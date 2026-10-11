# The generic client (`collibra_toolkit`)

`CollibraClient` knows how to authenticate to a Collibra environment and call its REST API v2. It knows nothing about any particular initiative.

```python
from collibra_toolkit import CollibraClient, CollibraNotFound

client = CollibraClient.from_env()        # COLLIBRA_URL + (COLLIBRA_USER, COLLIBRA_PASSWORD | COLLIBRA_TOKEN)
# or: CollibraClient("https://x.collibra.com", username="u", password="p")  /  token="..."

client.get_json("/communities", {"limit": 2})            # path is relative to /rest/2.0
for community in client.paginate("/communities"):         # follows offset/limit pages
    ...
resp = client.request("GET", "/assets/<id>", stream=False)   # raw response when you need it
```

## What it gives you

| Capability | Detail |
|---|---|
| Authentication | basic auth or bearer token; `from_env` reads the environment |
| Paths | relative to `/rest/2.0` |
| Redirects | followed (needed by pre-signed download URLs); `requests` drops the auth header on cross-host redirects |
| Errors | `CollibraHTTPError(status_code)` and subclasses `CollibraAuthError` (401/403), `CollibraNotFound` (404); network failures raise `CollibraError` with only the exception class name (messages can embed pre-signed URLs) |
| Pagination | `paginate(path, params, page_size=1000)` yields `results` items using Collibra's `{total, limit, results}` envelope; copes with servers capping the page size |
| Testing | pass your own `session` (anything with `request()`); see `tests/fakes.py` |

## Verification status

* **Verified on a live instance:** basic authentication, `GET /communities` envelope and multi-page pagination, 401 handling, the Insights download endpoint, `excludeMeta=false`, `GET /assets/{id}`, `/domains/{id}`, `/communities/{id}`, `/assetTypes`, and the `typeIds` asset filter.
* **Not yet verified:** token authentication, `GET /responsibilities?roleIds=…`, other endpoints, retry/back-off (none implemented).
* Pagination is only checked on `/communities`; endpoints that use cursor paging will need their own helper.

## Health check

`collibra-toolkit ping` (or `collibra-insights ping`) prints four lines proving reachability, response shape and pagination, with no content.

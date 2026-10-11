# The generic client (`collibra_toolkit`)

`CollibraClient` knows how to authenticate to a Collibra environment and call its REST API v2. It knows nothing about any particular initiative.

```python
from collibra_toolkit import CollibraClient, CollibraNotFound

client = CollibraClient.from_env()        # COLLIBRA_URL + OAuth, token or basic credentials (see below)
# or: CollibraClient("https://x.collibra.com", client_id="...", client_secret="...")   # OAuth (recommended)
#     CollibraClient("https://x.collibra.com", token="...")                            # static bearer token
#     CollibraClient("https://x.collibra.com", username="u", password="p")             # basic

client.get_json("/communities", {"limit": 2})            # path is relative to /rest/2.0
for community in client.paginate("/communities"):         # follows offset/limit pages
    ...
resp = client.request("GET", "/assets/<id>", stream=False)   # raw response when you need it
```

## What it gives you

| Capability | Detail |
|---|---|
| Authentication | OAuth 2.0 client credentials, static bearer token, or basic auth (see *Authentication*); `from_env` reads the environment |
| Paths | relative to `/rest/2.0` |
| Redirects | followed (needed by pre-signed download URLs); `requests` drops the auth header on cross-host redirects |
| Errors | `CollibraHTTPError(status_code)` and subclasses `CollibraAuthError` (401/403), `CollibraNotFound` (404), `CollibraRateLimitError` (429, with `retry_after`), `CollibraServerError` (5xx); network failures raise `CollibraError` with only the exception class name (messages can embed pre-signed URLs) |
| Pagination | `paginate(path, params, page_size=1000)` yields `results` items using Collibra's `{total, limit, results}` envelope; copes with servers capping the page size |
| Testing | pass your own `session` (anything with `request()`); see `tests/fakes.py` |

## Retries and rate limits

| Situation | What the client does |
|---|---|
| **429** | Retries any method (the request was not processed), honouring `Retry-After` (seconds or HTTP date) |
| **500 / 502 / 503 / 504** | Retries **only methods that are safe to repeat** (GET, HEAD, OPTIONS, PUT, DELETE). A POST is never repeated, since it may have been processed |
| Lost connection, timeout | Same rule as 5xx. SSL errors are permanent and are not retried |
| 4xx other than 429 | Never retried |
| Waiting | Exponential backoff with jitter (0.5 s, 1 s, 2 s, 4 s…), every wait capped at `max_wait` = 60 s; a server hint above the cap is shortened to it |
| Giving up | After `retries` (default 4) a typed error: `CollibraRateLimitError` or `CollibraServerError` |

Tune with `CollibraClient(..., retries=4, backoff=0.5, max_wait=60.0)`. A retry that follows a 401 token refresh does not count against these retries. Limits: a download that fails *midway through the body* is not resumed (only failures before the body starts are retried), and no request-rate throttling is done up front.

## Authentication

| Method | Environment variables | Use it when |
|---|---|---|
| **OAuth 2.0 client credentials** *(recommended)* | `COLLIBRA_CLIENT_ID`, `COLLIBRA_CLIENT_SECRET` | any client engagement or scheduled job |
| Static bearer token | `COLLIBRA_TOKEN` | you already hold a token (it will not be refreshed) |
| Basic | `COLLIBRA_USER`, `COLLIBRA_PASSWORD` | quick local tests |

Precedence when several are set: OAuth, then token, then basic. A client id without a secret is ignored.

**OAuth in practice.** In Collibra an administrator registers an *integration* OAuth application (Settings → OAuth Applications); Collibra then shows a client id and secret once. The client posts them to `/rest/oauth/v2/token` with `grant_type=client_credentials`, caches the access token, replaces it 60 seconds before it expires, and on a `401` fetches a new one and retries **once**. Per Collibra's documentation, tokens need no licence and actions are attributed to an application-specific system user, so the audit trail does not point at a person. The secret is only ever sent to the token endpoint, and never appears in error messages. Give the application only the permissions the job needs (for Insights: the right to download reporting data).

## Verification status

* **Verified on a live instance:** basic authentication, `GET /communities` envelope and multi-page pagination, 401 handling, the Insights download endpoint, `excludeMeta=false`, `GET /assets/{id}`, `/domains/{id}`, `/communities/{id}`, `/assetTypes`, and the `typeIds` asset filter.
* **Verified on a live instance (Oct 2026):** OAuth 2.0 client credentials with an *integration* application (`ping` reported `oauth`; token endpoint, parameters and Bearer use as documented). The same application also **downloaded an Insights snapshot**, so it needs the permission to download reporting data, and nothing more was required on the reference instance.
* **Implemented and unit-tested only:** static bearer tokens.
* **Implemented and unit-tested, not yet seen on a live instance:** retry/back-off for 429 and 5xx (no rate limiting has been observed yet).
* **Not yet verified:** other endpoints.
* Pagination is only checked on `/communities`; endpoints that use cursor paging will need their own helper.

## Health check

`collibra-toolkit ping` (or `collibra-insights ping`) prints five lines proving reachability, response shape, pagination and **which authentication method was really used** (`oauth`, `token` or `basic`), with no content. If you expect OAuth and it says `basic`, the client id or secret was empty and the client fell back silently.

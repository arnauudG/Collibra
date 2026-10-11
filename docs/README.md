# Collibra toolkit: documentation

A small, reusable Python toolkit for working with Collibra, built in layers: the generic client at the bottom, one folder per initiative on top. Each layer depends only on the layers below it, and a test enforces that.

| Layer | Package | Documentation |
|---|---|---|
| **Generic client**: auth, requests, typed errors, retries, pagination | `collibra_toolkit.client` | [client/README.md](client/README.md) |
| **Insights Data Access**: download snapshots, explore, model, query | `collibra_toolkit.insights` | [insights/README.md](insights/README.md) |
| *Your next initiative* | `collibra_toolkit.<name>` | see "Adding an initiative" |

## Layout: each level holds only what it needs

```
src/collibra_toolkit/
  _lazy.py                 lazy exports, so importing one layer never loads another
  client/                  THE GENERIC LAYER: knows no initiative; needs only `requests`
    retry.py   errors.py   auth.py   pagination.py   core.py (CollibraClient)   health.py
  cli/                     `collibra-toolkit`: generic commands + initiatives discovered by entry point
  insights/                ONE INITIATIVE: composes the client
    tables.py              pure data: the documented tables
    api/                   download (needs the client; no DuckDB)
    store/                 local DuckDB snapshot (needs nothing; no network)
    model/                 star schema + checks (needs store)
    diagnostics/           offline (needs store) and live (needs store + client)
    cli.py                 composition root: each command imports only the layers it needs
tests/                     mirrors src/; tests/support/ holds the shared HTTP fakes
docs/                      mirrors src/: docs/client/, docs/insights/
```

Inside `client/`, the order is `retry` → `errors` → `auth` → `pagination` → `core` → `health` (a module imports only the ones before it). `CollibraClient` is *composed* from an authenticator and a retry policy, so either can be swapped or tested alone.

## The rules (enforced by `tests/test_architecture.py`)

* The generic layer never imports an initiative; the generic CLI never imports one either (it discovers them).
* `requests` is imported only inside `client/`; `duckdb` only inside `insights/store/`.
* An initiative layer imports only the layers listed for it in that test.
* Downloading works without DuckDB; analysing a snapshot works without `requests`. Both are tested in a clean subprocess.

Install only what you need: `pip install -e .` (client), `pip install -e ".[insights]"` (adds DuckDB), `pip install -e ".[dev]"` (everything plus test tools).

## Adding an initiative

1. Create `src/collibra_toolkit/<name>/`. Give it a client class that **takes a `CollibraClient`** (composition, not inheritance) and calls `client.request`, `client.get_json` or `client.paginate`. Split it into layers the way `insights/` is; keep third-party dependencies in the layer that needs them.
2. Add a `cli.py` whose `main(argv)` is wrapped with `collibra_toolkit.cli.util.run`, and register it in `pyproject.toml`:
   ```toml
   [project.entry-points."collibra_toolkit.initiatives"]
   <name> = "collibra_toolkit.<name>.cli:main"
   ```
   `collibra-toolkit <name> …` then works with **no change to generic code**. Optionally add a script alias under `[project.scripts]`.
3. Add its rules to `ALLOWED` in `tests/test_architecture.py`, mirrored tests under `tests/<name>/` (use `tests/support/fakes.py` for HTTP), and docs under `docs/<name>/` with a README index.
4. Anything useful to more than one initiative belongs in the generic layer, not in the initiative.
5. Declare heavy dependencies as an extra (like `insights = ["duckdb"]`), not as a base dependency.

## Conventions

* Credentials come from `COLLIBRA_URL` plus `COLLIBRA_CLIENT_ID`/`COLLIBRA_CLIENT_SECRET` (OAuth, preferred), `COLLIBRA_TOKEN`, or `COLLIBRA_USER`/`COLLIBRA_PASSWORD`; never from command-line arguments.
* Documentation states what is **verified**, **documented by Collibra** or **inferred**.
* Exports contain personal data; downloaded data and diagnostic outputs are git-ignored.

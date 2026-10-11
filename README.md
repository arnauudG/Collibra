# collibra-toolkit

Reusable Python tooling for Collibra: a **generic REST client** that any initiative can build on and, so far, one initiative, **Insights Data Access** (download nightly snapshots, explore them locally with DuckDB, model them as a star schema, answer questions with SQL).

## Documentation

| Read | To |
|---|---|
| [**approach.md**](docs/insights/approach.md) | advise a client: the feasible modeling and the decisions a gold layer can support (**start here**) |
| [data-dictionary.md](docs/insights/data-dictionary.md) | know every table and column, how they join, how the data is delivered |
| [known-gaps.md](docs/insights/known-gaps.md) | avoid wrong totals: what the export omits and why |
| [modeling.md](docs/insights/modeling.md) | understand the silver star schema and why |
| [cookbook.md](docs/insights/cookbook.md) | answer real questions with 34 tested SQL recipes |
| [client-playbook.md](docs/insights/client-playbook.md) | apply it all at a new client, step by step |
| [docs/client/README.md](docs/client/README.md) | use the generic client (auth, retries, pagination) |

## Install

```bash
python3 -m venv ~/.venvs/collibra && . ~/.venvs/collibra/bin/activate    # keep the venv outside iCloud-synced folders
pip install -e ".[insights]"      # generic client + Insights (adds DuckDB). Client only: pip install -e .
```

## Use

```bash
export COLLIBRA_URL=https://<your-env>.collibra.com
# OAuth (recommended): an integration application registered by a Collibra administrator
export COLLIBRA_CLIENT_ID=<client id>
read -s COLLIBRA_CLIENT_SECRET     # on its own line; type or paste, Enter
export COLLIBRA_CLIENT_SECRET
# or basic auth: export COLLIBRA_USER=<user>; read -s COLLIBRA_PASSWORD; export COLLIBRA_PASSWORD

collibra-toolkit ping                                  # generic: credentials, pagination, auth method used
collibra-insights tables-available 2026-10-10 --endpoint both
collibra-insights download 2026-10-10                  # -> snapshots/insights-2026-10-10/
collibra-insights explore  snapshots/insights-2026-10-10
collibra-insights check    snapshots/insights-2026-10-10
collibra-insights investigate snapshots/insights-2026-10-10 --live
collibra-insights query    snapshots/insights-2026-10-10 --model --file q.sql
collibra-insights export   snapshots/insights-2026-10-10 --out lake      # optional: bronze/silver/gold Parquet
```
(`collibra-toolkit insights …` is the same as `collibra-insights …`. Point `explore`/`query` at a parent folder to load several snapshots at once for history.)

```python
from collibra_toolkit import CollibraClient
from collibra_toolkit.insights import InsightsClient, Snapshot, build_model

client = CollibraClient.from_env()                       # generic, reusable
folder = InsightsClient(client).download_snapshot("2026-10-10", "snapshots")
snap = Snapshot(folder); build_model(snap)
snap.sql("select asset_type_name, count(*) from dim_asset group by 1").fetchall()
```

## Layout: each level holds only what it needs

```
src/collibra_toolkit/
  _lazy.py       lazy exports, so importing one layer never loads another
  client/        THE GENERIC LAYER: knows no initiative; needs only `requests`
                 retry -> errors -> auth -> pagination -> core (CollibraClient) -> health
  cli/           `collibra-toolkit`: generic commands; initiatives are discovered by entry point
  insights/      ONE INITIATIVE: composes the client
    tables.py    pure data: the documented tables
    api/         download (needs the client; no DuckDB)
    store/       local DuckDB snapshot (needs nothing; no network)
    model/       star schema, checks, gold tables (needs store)
    diagnostics/ offline (needs store) and live (needs store + client)
    lakehouse/   optional bronze/silver/gold Parquet output (needs store + model)
    cli.py       composition root: each command imports only the layers it needs
tests/           mirrors src/; tests/support/ holds the shared HTTP fakes
docs/            mirrors src/: docs/client, docs/insights
```

**Rules, enforced by `tests/test_architecture.py`:** the generic layer never imports an initiative (the generic CLI *discovers* them); `requests` is imported only inside `client/`, `duckdb` only inside `insights/store/`; each layer imports only the layers listed for it. Downloading works without DuckDB, and analysing a snapshot works without `requests`; both are tested in a clean subprocess. Install only what you need: `pip install -e .` (client), `".[insights]"` (adds DuckDB), `".[dev]"` (adds test tools).

## Adding an initiative

1. Create `src/collibra_toolkit/<name>/` with a client class that **takes a `CollibraClient`** (composition, not inheritance) and calls `client.request`, `client.get_json` or `client.paginate`. Split it into layers like `insights/`; keep each third-party dependency in the layer that needs it.
2. Add a `cli.py` whose `main(argv)` is wrapped with `collibra_toolkit.cli.util.run`, and register it in `pyproject.toml`:
   ```toml
   [project.entry-points."collibra_toolkit.initiatives"]
   <name> = "collibra_toolkit.<name>.cli:main"
   ```
   `collibra-toolkit <name> …` then works with no change to generic code.
3. Add its rules to `ALLOWED` in `tests/test_architecture.py`, mirrored tests under `tests/<name>/` (HTTP fakes in `tests/support/fakes.py`) and docs under `docs/<name>/`.
4. Anything useful to more than one initiative belongs in the generic layer. Declare heavy dependencies as an extra, not a base dependency.

## Conventions and status

* Credentials come from environment variables, never from arguments. Downloaded data, diagnostic outputs and `lake/` are git-ignored: they contain instance data.
* Documentation states what is **verified**, **documented by Collibra** or **inferred**.

| Piece | State |
|---|---|
| Generic client: basic auth, **OAuth client credentials**, pagination | Verified live on one instance; static token untested; retry/back-off unit-tested only |
| Insights download, explorer, model, checks, diagnostics | Verified live on one instance; also unit-tested with fake HTTP and synthetic data |
| `export` (bronze/silver/gold Parquet) | Unit-tested on synthetic data; **not yet run on a real snapshot** |
| `view_events` and the Usage Analytics recipes | Built from Collibra's documentation; **no real data to verify** |
| Cookbook SQL | Every query is executed by the tests against a fixture; not all run on real data |

Requires Collibra Platform 5.7+ and an Insights licence.

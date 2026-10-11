# collibra-toolkit

Reusable Python tooling for Collibra: a **generic REST client** that any initiative can build on, and, so far, one initiative package, **Insights Data Access** (download nightly snapshots, explore them locally with DuckDB, model them as a star schema, answer questions with SQL).

* Toolkit documentation: [`docs/README.md`](docs/README.md)
* Insights documentation (start here for colleagues): [`docs/insights/README.md`](docs/insights/README.md), including a step-by-step [client playbook](docs/insights/client-playbook.md)

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

collibra-toolkit ping                                  # generic: credentials + pagination
collibra-insights tables-available 2026-10-10 --endpoint both
collibra-insights download 2026-10-10                  # -> snapshots/insights-2026-10-10/
collibra-insights explore  snapshots/insights-2026-10-10
collibra-insights check    snapshots/insights-2026-10-10
collibra-insights investigate snapshots/insights-2026-10-10 --live
collibra-insights query    snapshots/insights-2026-10-10 --model --file q.sql
```
(`collibra-toolkit insights …` is the same as `collibra-insights …`. Point `explore`/`query` at a parent folder to load several snapshots at once.)

```python
from collibra_toolkit import CollibraClient
from collibra_toolkit.insights import InsightsClient, Snapshot, build_model

client = CollibraClient.from_env()                       # generic, reusable
folder = InsightsClient(client).download_snapshot("2026-10-10", "snapshots")
snap = Snapshot(folder); build_model(snap)
snap.sql("select asset_type_name, count(*) from dim_asset group by 1").fetchall()
```

## Layout

```
src/collibra_toolkit/
  client/        the generic layer: retry, errors, auth, pagination, core (CollibraClient), health
  cli/           `collibra-toolkit`: generic commands; initiatives are discovered by entry point
  insights/      one initiative: tables, api/ (download), store/ (DuckDB), model/, diagnostics/, cli.py
tests/           mirrors src/ (tests/client, tests/insights/...), shared fakes in tests/support/
docs/            mirrors src/ (docs/client, docs/insights)
```
Each layer depends only on the layers below it; `tests/test_architecture.py` enforces it. See [`docs/README.md`](docs/README.md).

## Status (honest)

| Piece | State |
|---|---|
| Generic client: auth, typed errors, pagination | Basic auth, **OAuth client credentials** and pagination verified live on one instance; static token untested; retry/back-off unit-tested only |
| Insights download, extraction, explorer, model, checks | Verified live on one instance; unit-tested with fake HTTP and synthetic data |
| `view_events` / `fact_view_event` / Usage Analytics recipes | Built from Collibra's documentation; **no real data available to verify** |
| Cookbook SQL | Every query is executed by the tests against a fixture; not all run on real data |

Requires Collibra Platform 5.7+ and an Insights licence. Snapshots contain sensitive data and are git-ignored.

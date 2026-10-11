# collibra-insights

A small Python package to **download Collibra Insights Data Access snapshots** and **explore them locally** with DuckDB. Companion guides explain what the data is and how to model it:

- [`docs/insights-data-access.md`](docs/insights-data-access.md): what Insights Data Access is, how it is delivered, retention, and the tables
- [`docs/data-modeling.md`](docs/data-modeling.md): how to model the tables (dimensions, facts, snapshots, pivoting attributes)

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

export COLLIBRA_URL=https://<your-env>.collibra.com
export COLLIBRA_USER=...  COLLIBRA_PASSWORD=...     # or COLLIBRA_TOKEN=...

collibra-insights download 2026-10-10                # -> snapshots/insights-2026-10-10/
collibra-insights explore snapshots/insights-2026-10-10
collibra-insights query snapshots/insights-2026-10-10 "select count(*) from asset"
collibra-insights check snapshots/insights-2026-10-10   # build the model + conformance report
collibra-insights ping                                  # live check: credentials + pagination
```

```python
from collibra_insights import Snapshot
s = Snapshot("snapshots/insights-2026-10-10")
print(s.report())                       # every table, row count, columns + types
s.sql("select count(*) from asset").fetchall()
```

## Layers

Each layer works alone and builds on the one above it:

| Module | Responsibility | Knows about Insights? |
|---|---|---|
| `client.CollibraClient` | auth, requests, typed errors, `paginate` | no |
| `insights.InsightsClient(client)` | snapshot download, retention check, safe extraction | yes |
| `explore.Snapshot(path)` | local DuckDB views over a snapshot folder; **no network** | yes |
| `model.build_model(snapshot)` | star-schema views, `check_model` | yes |

```python
from collibra_insights import CollibraClient, InsightsClient

client = CollibraClient.from_env()                  # reusable for any REST 2.0 endpoint
for community in client.paginate("/communities"):   # pagination verified live on this endpoint
    ...
folder = InsightsClient(client).download_snapshot("2026-10-10", "snapshots")
```

## Status (honest)

| Piece | State |
|---|---|
| Generic client (auth, typed errors, pagination) | Implemented, tested against **fake** HTTP. `paginate` verified live on `/communities` only (envelope and multi-page walk as assumed); other endpoints untested |
| Insights download, safe unzip, DuckDB views, schema discovery | Implemented, unit-tested against **fake** HTTP and **synthetic** Parquet |
| Run against a real Collibra environment | **Done once** (training instance, snapshot 2026-10-10): download + explore of all 8 tables worked |
| Column-level schema | Observed and documented in `docs/data-modeling.md`; still **discovered at runtime**, not hardcoded |
| Table grain, relation direction, community repeats | **Verified** on the real snapshot. Still open: `attribute.kind` → value column mapping, meaning of `community.level` (`docs/data-modeling.md` §5) |
| Star-schema views + `check` | Implemented (`model.py`), tested on **synthetic** data with real column names; not yet run on the real snapshot |

Requires Collibra Platform 5.7+ and a Collibra Insights licence. Snapshots may contain sensitive governance data and are git-ignored.

## Investigating the export

`collibra-insights investigate <snapshot>` prints aggregate evidence on open questions (file layout, attribute `kind` mapping, `community.level`, Issue-related orphans, unresolved responsibilities). Add `--live` to compare against the REST API of the same instance (totals, per-type counts, and what unresolved ids actually are). Output contains counts, type names and id prefixes only. Findings are recorded in `docs/data-modeling.md`.

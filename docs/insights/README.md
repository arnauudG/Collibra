# Insights Data Access

Insights Data Access is Collibra's add-on that copies a catalogue's metadata (communities, domains, assets, attributes, relations, responsibilities, optionally Usage Analytics events) **every night** into a snapshot you download as Parquet files. This initiative downloads those snapshots, takes them apart, models them as a star schema, and shows which business questions and decisions they support.

Requires Collibra Platform 5.7+ and an Insights licence. Install with `pip install -e ".[insights]"` (adds DuckDB; downloading alone needs only the base install). Credentials: see the [root README](../../README.md#connect).

## Read in this order

| Read | To |
|---|---|
| [**approach.md**](approach.md) | advise a client: the feasible modeling and the decisions a gold layer can support (**start here**) |
| [known-gaps.md](known-gaps.md) | avoid wrong totals: what the export omits and why |
| [data-dictionary.md](data-dictionary.md) | know every table and column, how they join, how the data is delivered |
| [modeling.md](modeling.md) | understand the star schema and why |
| [cookbook.md](cookbook.md) | answer real questions with 34 tested SQL recipes |
| [client-playbook.md](client-playbook.md) | apply it all at a new client, step by step |

## Commands

```bash
collibra-insights tables-available 2026-10-10 --endpoint both    # what a snapshot ZIP contains, without extracting
collibra-insights download 2026-10-10                            # -> snapshots/insights-2026-10-10/
collibra-insights explore  snapshots/insights-2026-10-10         # tables, row counts, columns
collibra-insights profile  snapshots                             # what the catalogue contains and says (+ changes between the last two)
collibra-insights check    snapshots/insights-2026-10-10         # conformance of the model
collibra-insights investigate snapshots/insights-2026-10-10 --live   # export compared with the live API
collibra-insights query    snapshots/insights-2026-10-10 --model --file q.sql
```
`collibra-toolkit insights …` is equivalent. Point `explore`, `profile` or `query` at a parent folder to load several snapshots at once (history).

```python
from collibra_toolkit import CollibraClient
from collibra_toolkit.insights import InsightsClient, Snapshot, build_model

folder = InsightsClient(CollibraClient.from_env()).download_snapshot("2026-10-10", "snapshots")
snap = Snapshot(folder)
build_model(snap)
snap.sql("select asset_type_name, count(*) from dim_asset group by 1").fetchall()
```

## How the code is layered

| Folder (`src/collibra_toolkit/insights/`) | Job | Needs |
|---|---|---|
| `tables.py` | the documented tables | nothing |
| `api/` | download snapshots | the generic client (no DuckDB) |
| `store/` | read a snapshot locally | DuckDB only (no network) |
| `model/` | star schema and conformance checks | `store` |
| `diagnostics/` | evidence about an export: `offline`, `profile`, and `live` | `store` and `model` (+ the client for `live`) |
| `cli.py` | `collibra-insights` | composes the layers above |

## Status

| Piece | State |
|---|---|
| Download, explore, check, investigate `--live`, profile | Verified live on one (training) instance |
| Model and conformance checks | Verified on that instance; also unit-tested on synthetic data with the real column names |
| Cookbook recipes | Every query runs in the tests against a fixture; not all have been run on real data |
| `view_events` and the Usage Analytics recipes | Absent from the reference tenant; built from Collibra's documentation only |

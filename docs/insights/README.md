# Collibra Insights Data Access: documentation

Insights Data Access is a **nightly copy of a Collibra catalogue** (communities, domains, assets, attributes, relations, responsibilities, optionally Usage Analytics events) that you download as Parquet files and analyse with SQL. Think of it as a daily photograph of the catalogue: great for reporting and history, not live.

This documentation is **instance-independent**: it explains Insights in general and shows how to apply it to any client. Numbers from the reference instance are labelled as examples.

**Advising a client? Read [approach.md](approach.md) first**: one page on the feasible modeling and the decisions a gold layer can support.

## Read in this order

| # | Document | Read it to… | Time |
|---|---|---|---|
| 1 | [Overview](overview.md) | understand what it is, delivery, retention | 5 min |
| 2 | [Use cases](use-cases.md) | see which business questions and decisions Insights supports, and which it cannot | 10 min |
| 3 | [Data dictionary](data-dictionary.md) | know every table and column, keys, how they join | 15 min |
| 4 | [Known gaps](known-gaps.md) | avoid wrong totals: what the export omits and why | 10 min |
| 5 | [Modeling guide](modeling.md) | understand the star schema and why | 10 min |
| 6 | [Cookbook](cookbook.md) | answer real questions with tested SQL | as needed |
| 7 | [Medallion architecture](medallion.md) | land, model and serve Insights as bronze/silver/gold data products | 15 min |
| ★ | [Client playbook](client-playbook.md) | apply all of this at a new client, step by step | 1 hour |

**Just want an answer?** Jump to the [cookbook](cookbook.md) (28 tested recipes), but read each "Watch out". **Wondering what this is good for?** Start with [use cases](use-cases.md).

## Five things to remember

1. **A snapshot is yesterday's photo**, taken nightly in UTC. Every table has a `snapshot_date`, and every join must include it.
2. **Raw tables are not analysis-ready.** `relation` stores each link twice, `community` repeats a row per level, `attribute` is one long list. Count on the **model** (`dim_*`, `fact_*`).
3. **Join on ids, never names.**
4. **The export is not identical to the UI.** Hidden built-in "meta" objects are partly included, partly omitted; some responsibilities point at non-catalog resources. Keep unmatched rows (`LEFT JOIN`).
5. **Responsibilities and view events contain personal data.** The model hides names and emails unless asked.

## Glossary

| Term | Meaning |
|---|---|
| Snapshot | One day's copy of the data, delivered as a ZIP of Parquet files |
| Grain | What one row of a table represents |
| Dimension (`dim_*`) | A table of things you group by: assets, domains, communities, users |
| Fact (`fact_*`) | A table of events or measurements you count |
| EAV | Entity-attribute-value: one generic table holds every attribute of every asset |
| Meta object | A built-in Collibra helper object hidden from the normal API list; partly present in the export |
| Resource role | A role (Owner, Data Quality Manager…) that applies to a resource and its children through a responsibility |
| Orphan | A row whose parent id does not exist in the exported tables |

## How the code is layered

| Folder (`src/collibra_toolkit/insights/`) | Job | Needs |
|---|---|---|
| `tables.py` | the documented tables | nothing |
| `api/` | download snapshots | the generic client (no DuckDB) |
| `store/` | read a snapshot locally | DuckDB only (no network) |
| `model/` | star schema and conformance checks | `store` |
| `diagnostics/` | evidence about an export: `offline` and `live` | `store` (+ the client for `live`) |
| `lakehouse/` | write bronze (raw), silver (model) and gold as Parquet | `store`, `model` |
| `cli.py` | `collibra-insights` | composes the layers above |

So a scheduled downloader needs no DuckDB, and analysing a snapshot on a locked-down machine needs no network libraries.

## Commands

```bash
collibra-insights ping                              # credentials and pagination
collibra-insights tables-available <dates> --endpoint both
collibra-insights download <date>
collibra-insights explore  <snapshot>
collibra-insights check    <snapshot>
collibra-insights investigate <snapshot> [--live]
collibra-insights query    <snapshot> --model --file q.sql
collibra-insights export   <snapshot> --out lake [--layer gold] [--gold-config gold.json]
```

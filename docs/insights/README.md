# Collibra Insights Data Access: documentation

Insights Data Access is a **nightly copy of your Collibra catalogue** (communities, domains, assets, attributes, relations, responsibilities) that you download as Parquet files and analyse with SQL. Think of it as a daily photograph of your catalogue: great for reporting and history, not live.

## Read in this order

| # | Document | Read it to… | Time |
|---|---|---|---|
| 1 | [Overview](insights-data-access.md) | understand what it is, how data is delivered, retention | 5 min |
| 2 | [Data dictionary](data-dictionary.md) | know every table and column, how they join, what a row means | 15 min |
| 3 | [Known gaps](known-gaps.md) | avoid wrong totals: what the export omits and why numbers differ from the UI | 5 min |
| 4 | [Modeling guide](data-modeling.md) | understand the star schema built on top, and why | 10 min |
| 5 | [Cookbook](cookbook.md) | answer real questions with copy-paste SQL | as needed |

**Just want an answer?** Jump to the [cookbook](cookbook.md), but read the "Watch out" notes.

## Five things to remember

1. **A snapshot is yesterday's photo**, taken nightly in UTC. Every table has a `snapshot_date`.
2. **Raw tables are not analysis-ready.** `relation` stores every link twice; `community` repeats a row per hierarchy level; `attribute` is one long list of every value. Count on the **model** (`dim_*`, `fact_*`), not the raw tables.
3. **Join on ids, never names.**
4. **The export is not identical to the UI.** Some built-in "meta" objects are included, others omitted ([known gaps](known-gaps.md)). Keep unmatched rows (`LEFT JOIN`) instead of dropping them.
5. **Responsibilities contain personal data** (names, emails). The model hides them unless you ask.

## Glossary

| Term | Meaning |
|---|---|
| Snapshot | One day's copy of the data, delivered as a ZIP of Parquet files |
| Grain | What one row of a table represents (e.g. "one asset", "one relation per direction") |
| Dimension (`dim_*`) | A table of things you group by: assets, domains, communities, users |
| Fact (`fact_*`) | A table of events or measurements you count: attribute values, relations, responsibilities |
| EAV | Entity-attribute-value: one generic table holds every attribute of every asset, so it must be pivoted for reporting |
| Meta object | A built-in Collibra helper object hidden from the normal API list; partly present in the export |
| Orphan | A row whose parent id does not exist in the exported tables |

## Getting started

```bash
pip install -e ".[dev]"
export COLLIBRA_URL=https://<your-env>.collibra.com COLLIBRA_USER=<you>
read -s COLLIBRA_PASSWORD       # type it, press Enter (nothing is shown)
export COLLIBRA_PASSWORD
collibra-insights download 2026-10-10           # yesterday or a recent date
collibra-insights explore snapshots/insights-2026-10-10   # tables and columns
collibra-insights check snapshots/insights-2026-10-10     # data-quality report
```

Prerequisites: Collibra Platform 5.7+ and an Insights licence.

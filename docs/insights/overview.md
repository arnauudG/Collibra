# Insights Data Access: overview

Insights Data Access is Collibra's **paid add-on that captures your reporting data every night and lets you download it**. It retains history without touching front-end performance. Sources: Collibra's *Insights Data Access*, *Reporting data*, *Insights tables*, *Entity relationship diagram* and *Set up Insights* pages in the Product Resource Center.

## The idea in one paragraph

Each night Collibra copies assets, attributes, relations, responsibilities and more into a **snapshot**. You cannot query that copy inside Collibra. A REST endpoint hands you a **ZIP of Parquet files** for a chosen date; you load them into a warehouse (Athena on AWS, BigQuery on GCP, Databricks Lakebase) or, as this toolkit does, query them locally. It is a daily photograph of your catalogue, not a live API.

## Prerequisites

Collibra Platform **5.7 or newer** and a **Collibra Insights licence**. Usage Analytics (the free dashboard) is a different product: it needs no setup, refreshes every 2 hours and has no public API of its own; Insights Data Access is how its events are exposed.

## Delivery

| Endpoint (relative to `/rest/2.0`) | Notes |
|---|---|
| `/reporting/insights/directDownload?snapshotDate=YYYY-MM-DD&format=zip` | Recommended. Answers with a redirect to a **pre-signed storage URL valid ~60 s**, so the HTTP client must follow redirects. Works on AWS and GCP |
| `/reporting/insights/download?...` | Legacy; documented as soon to be deprecated |

The date needs the full `YYYY-MM-DD` format.

## Timing and retention

* Processing happens in **UTC**; "ready" times vary by region (roughly 05:00–13:00 UTC, one region as early as 01:00; see Collibra's *Reporting data* table). Request **yesterday's** snapshot, not today's.
* Retention: every daily snapshot for **31 days**, then the last snapshot of each **month** for 12 months, then the last of each **year** indefinitely.
* Each record carries the snapshot date, so several snapshots can sit in one table (history).

## Tables

Eight tables are loaded by Collibra's setup guides: `community`, `domain`, `asset`, `asset_tag`, `attribute`, `relation`, `complex_relation`, `responsibility`. A ninth, `view_events` (Usage Analytics), is documented but optional. Details and columns: [data-dictionary.md](data-dictionary.md).

## What it does not give you

See [known-gaps.md](known-gaps.md): excluded types, community-inherited responsibilities, hidden built-in objects, Data Quality resources, UI-only view events.

## Where to go next

What can you decide with it? See [use-cases.md](use-cases.md). New to a client? Follow the [client playbook](client-playbook.md).

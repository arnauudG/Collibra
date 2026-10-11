# Insights Data Access: what it is

Everything below comes from Collibra's Product Resource Center (pages fetched 2026-10-11): [Insights Data Access](https://productresources.collibra.com/docs/collibra/latest/Content/Reporting/to_insights-data-access-intro.htm), [Reporting data](https://productresources.collibra.com/docs/collibra/latest/Content/Reporting/co_working-with-data.htm), [Insights tables](https://productresources.collibra.com/docs/collibra/latest/Content/Reporting/co_insights-data-access-tables.htm), [Set up on GCP](https://productresources.collibra.com/docs/collibra/latest/Content/Reporting/ta_create-insights-data-access-gcp.htm), [Set up on AWS](https://productresources.collibra.com/docs/collibra/latest/Content/Reporting/ta_create-insights-data-access-aws.htm).

## The idea in one paragraph

Collibra copies your reporting data **every night** into a snapshot. You can't query that copy directly inside Collibra; instead a REST endpoint hands you a **ZIP of Parquet files** for a chosen date. You load those files into a warehouse (Athena on AWS, BigQuery on GCP, Databricks Lakebase) or, as in this package, just query them locally. Think of it as a daily photograph of your catalogue, not a live API.

## Delivery

- Endpoint: `GET <env-url>/rest/2.0/reporting/insights/directDownload?snapshotDate=YYYY-MM-DD&format=zip`
- It **redirects** to a pre-signed cloud-storage URL valid ~60 s by default, so your HTTP client must follow redirects. `/insights/download` is documented as soon-to-be-deprecated.
- Requirements: Collibra Platform 5.7+, a Collibra Insights licence (the docs note it is not a free, out-of-the-box product).

## Retention

| Window | Snapshots kept |
|---|---|
| Last 31 days | every daily snapshot |
| Last 12 months | last snapshot of each month |
| Older than 1 year | last snapshot of each year, indefinitely |

The date you request must be within the last 31 days **or** a month-end (the client checks this up front). Processing runs in UTC; "data ready" times vary by cloud region (e.g. AWS London ~06:00 UTC, GCP Virginia ~10:00 UTC). Request yesterday's snapshot, not today's.

## Tables

The docs list these (the ZIP holds one folder of Parquet per table; the GCP guide shows eight folders):

| Folder | Holds |
|---|---|
| `community` | Community hierarchy |
| `domain` | All domains |
| `asset` | All assets, incl. custom asset types |
| `asset_tag` | Asset tags |
| `attribute` | Attributes of assets (Definition, Description, custom types) |
| `relation` | Binary relations (e.g. categorizes / is categorized by), incl. custom types |
| `complex_relation` | Complex (n-ary) relations |
| `responsibility` | Owner, Stakeholder, etc. for a resource |
| *(folder name not documented)* | Usage Analytics view events: page visits per user session |

**Exclusions:** asset types not manageable through the Asset Type Operating Model (e.g. Roles, Workflow Definitions) are excluded, along with their attributes, communities, domains, and relations.

**Privacy:** Usage Analytics data can be subject to access restrictions in your organisation; get approval before using it.

## Not documented publicly

Column names and types. They are in the Marketplace SQL scripts and in the Parquet files. Run `collibra-insights explore <snapshot>` once on real data and record them in [`data-modeling.md`](data-modeling.md).

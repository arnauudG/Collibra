# What an Insights export does and does not contain

Read this before trusting a total. Sections 1 and 2 apply to **any** Collibra instance; section 3 shows how to measure your own; the appendix gives real numbers from one reference instance as an example, not as a rule.

## 1. By design (documented by Collibra)

| Rule | Consequence |
|---|---|
| Asset types not manageable through the **Asset Type Operating Model** (e.g. Roles, Workflow Definitions) are excluded, with their attributes, communities, domains and relations | Some ids referenced elsewhere have no row in your tables |
| **Responsibilities** include those assigned directly to assets and those **inherited from domains** (as rows on the domain's assets). **Community-inherited responsibilities are excluded.** A null `asset_id` is a **global permission** | "Who owns this asset?" is right for asset- and domain-level ownership, but misses ownership set at community level |
| Resource roles also attach to **non-catalog resources**, notably **Data Quality jobs and connections** (roles *Data Quality Manager / Editor / Viewer*) | Those rows have a `resource id` that is not an asset, domain or community, so they never join (see 2c) |
| Collibra says the `domain` table holds domains "that contain assets" | **Not reliable**: the reference export also held empty domains (232 of 585, mostly built-in *Issues Vocabulary* domains, 46 of them ordinary); `investigate` prints your count |
| `view_events` is a documented table but **not** one of the eight tables in the setup guides; it only counts **UI** events since Usage Analytics was enabled | See 2d |
| Snapshots are **nightly** copies, processed in UTC; kept daily for 31 days, then month-ends for a year, then year-ends | Never a live view |
| `community` repeats a row per ancestor level; `relation` stores each link twice | Use the model (`dim_community`, `fact_relation`) |

## 2. Patterns you will probably meet

### a. A few rows whose parent is missing
Some assets point at a `domain_id` absent from `domain`; some domains point at a community absent from `community`. Cause (observed): Collibra has hidden built-in **"meta" objects** that its normal list API skips; the export includes some and omits others. The missing parents are omitted built-in objects with system-style ids (`00000000-0000-…`).
**Do:** keep the rows (`LEFT JOIN`). The model flags them (`dim_asset.is_domain_missing`).

### b. Export totals differ from the UI and the API
The export can hold more than the default API list (hidden meta objects it includes) and less than the API with `excludeMeta=false` (meta objects it omits). Reconcile with the three-way table in section 3 before reporting a mismatch.

### c. Responsibilities that match no asset
Four different causes; tell them apart with `collibra-insights investigate <snapshot> --live`:

| Cause | How to recognise it | Status |
|---|---|---|
| **Data Quality roles** (*Data Quality Manager / Editor / Viewer*) on jobs and connections | one row per job; the users are the job creators (the creator is auto-granted Manager; jobs inherit from their connection); the id returns 404 as asset, domain and community; the responsibilities API reports the resource type as `BaseDataType`, a generic non-catalog type | Documented by Collibra; **confirmed live** on the reference instance |
| **Global permissions** | `asset_id` is null | Documented by Collibra |
| **Domain-level responsibilities expanded onto hidden assets** | a role with thousands of asset rows held by one or two users, while the responsibilities API shows only a handful of assignments (on domains or communities); the sampled assets belong to domains that are not in the export | Consistent with Collibra's rule that domain-inherited responsibilities are expanded onto assets; `investigate --live` tests it directly (`domain-level expansion test`). **Reference instance: confirmed for the sample** (all 15 sampled assets sit in one domain on which the role is assigned directly; the role has 3 domain-level assignments in the API); extending it to all rows is inference |
| Responsibilities on assets the export omits | the asset id exists live but is in no exported table | Observed |

**Do:** analyse ownership of real assets with `fact_responsibility.asset_resolution = 'in_export'`. Don't treat the rest as errors.

**Direct and inherited rows look identical.** The export has no column saying whether a responsibility was assigned on the asset or inherited from its domain. One domain-level assignment becomes one row per asset in the domain, so a handful of assignments can dominate any "responsibilities per person" count. The cookbook recipe *Which responsibilities look like domain-level assignments?* lists the person-role pairs that cover 100% of a domain, which are almost certainly domain-level assignments.

### d. No Usage Analytics table
`view_events` may simply not be in your ZIP. Collibra's own setup guides only load eight tables, and the documentation does not say what makes `view_events` appear.

Check with `collibra-insights tables-available <dates> --endpoint both`. On the reference instance it was **absent on both download endpoints (`directDownload` and the legacy `download`) and on both a recent date and a month-end**, which rules out the endpoint and the date as causes. What remains is that it is **not provisioned for the tenant**, which only the client's Collibra administrator or Collibra support can confirm. Ask: *"Is the Usage Analytics view-events table enabled in our Insights Data Access export?"* (Also check that Usage Analytics itself shows data in the product.) When the table is present the model exposes it as `fact_view_event` and the cookbook has recipes ready (section *Usage Analytics*).
Status on the reference instance: cause **unconfirmed**; needs the administrator.

## 3. Measure it on your own instance

```bash
collibra-insights check        <snapshot>          # model conformance: orphans, duplicates
collibra-insights investigate  <snapshot>          # offline: kinds, levels, unresolved responsibilities
collibra-insights investigate  <snapshot> --live   # compares export to the REST API (needs credentials)
```
`--live` prints, for communities, domains and assets: **live default**, **live including meta** (`excludeMeta=false`), and **export** counts, plus what a spread sample of unresolved responsibility ids actually are, and which domain kind they live in. Interpret it with this recipe:

* hidden by default = live-incl-meta − live-default
* meta objects the export includes ≈ export − live-default
* meta objects the export omits ≈ live-incl-meta − export (assumes the export is a subset of live-incl-meta)

## Appendix: reference measurements (one training instance, October 2026)

Illustration only; your numbers will differ.

| | Live default | Live incl. meta | Export | Omitted by export |
|---|---|---|---|---|
| Communities | 187 | 189 | 187 | 2 |
| Domains | 398 | 590 | 585 | 5 |
| Assets | 23,099 | 28,224 | 23,202 | 5,022 |

* The export included 187 *Issues Vocabulary Type* domains, 101 *Data Usage* and 2 *Data Issue* assets that the default API list hides.
* 14 assets (all *Issue Category*) and 1 domain had a missing parent (an *Issue Classification* domain and a community with system-style ids, both existing live).
* 5,027 of 20,036 responsibilities matched no asset: 4,904 *Community Manager* rows held by one user (the responsibilities API showed only 5 such assignments, on 2 communities and 3 domains; the sampled assets sat in hidden domains), 122 *Data Quality Manager* rows (13 users, ids unique per row, 404 as asset/domain/community, API resource type `BaseDataType`) and 1 *Data Quality Viewer*. Another 47 rows had a null `asset_id` (global permissions).
* No `view_events` table in the ZIP (eight folders, only `.parquet`), on both endpoints and on two dates.

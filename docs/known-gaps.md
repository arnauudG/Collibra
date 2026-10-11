# What the Insights export does not contain

Read this before trusting a total. Evidence comes from comparing a real snapshot (2026-10-10) with the same instance's REST API (`collibra-insights investigate --live`). Each point carries its confidence.

## The short version

Collibra has hidden **"meta" objects** (built-in helper objects that its normal list API skips). The export contains **some** of them and **omits others**. A few rows therefore point at things that are not in the tables. This is expected, not corruption.

| | Live API (default) | Live API incl. meta | Export | In live-incl-meta but not exported |
|---|---|---|---|---|
| Communities | 187 | 189 | 187 | 2 |
| Domains | 398 | 590 | 585 | 5 |
| Assets | 23,099 | 28,224 | 23,202 | 5,022 |

(The last column assumes the export is a subset of "live incl. meta", which is very likely but unproven.)

## What it means in practice

| You will see… | Why | What to do |
|---|---|---|
| 14 assets whose `domain_id` is not in `domain` (all type *Issue Category*) and 1 domain whose community is missing | Their parents are omitted built-in objects (ids starting `00000000-`; confirmed to exist live) | Keep the rows (`LEFT JOIN`). `dim_asset.is_domain_missing` flags them |
| ~5,000 responsibilities whose `asset_id` is not an exported asset | 4,904 are **Community Manager** rows, all held by **one user**, pointing at hidden meta assets (a spread sample of 15: 13 *Assignment Characteristics*, 2 *Articulation Scores*) | Filter on `fact_responsibility.asset_resolution = 'in_export'` for ownership analysis |
| 123 responsibilities (122 *Data Quality Manager*, 1 *Data Quality Viewer*) that are neither assets, domains nor communities | **Unknown.** All 16 sampled ids return 404 on the asset, domain and community endpoints; plausibly Data Quality resources | Treat as unexplained; exclude from ownership analysis |
| 187 domains of type *Issues Vocabulary Type*, 101 *Data Usage* and 2 *Data Issue* assets that the API list does not show | Included meta objects | Exclude by type name if you only want what users see in the UI |
| Export totals larger than what the API reports | The same, see above | Compare with the table above before reconciling |

## Confidence

| Finding | Confidence |
|---|---|
| Counts in the table above | High (measured) |
| The export includes some meta objects and omits others | High |
| Orphans are children of omitted built-in objects | High |
| Community Manager rows point at hidden meta assets | Medium-high (sample of 15 of 4,904) |
| *Why* some meta objects are omitted: consistent with Collibra's rule that asset types not manageable through the Asset Type Operating Model are excluded | **Unverified** |
| 47 responsibilities with no `asset_id` are global role assignments | Low (inferred) |
| Cause of the missing Usage Analytics table | **Unknown** |

## Other limits worth knowing

- **Inherited ownership is not visible.** No responsibility row references a domain or community.
- **No user directory.** Only users holding at least one responsibility appear.
- **No relation-type names**, only ids and role labels.
- **Snapshots are daily copies, not live.** The newest one is yesterday's, processed in UTC; "ready" times vary by region (roughly 05:00-13:00 UTC).
- **Retention:** every day for 31 days, then month-ends for a year, then year-ends.

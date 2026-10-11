# What Insights supports: business questions and decisions

Insights is a **history of your catalogue's metadata**: what exists, who is responsible, how it is connected and described, and how that changed from one snapshot to the next. It is not live, and it is not about the data *inside* your systems. This page maps the questions it can answer to the decisions they support, the model objects each needs, and what it cannot do.

## 1. Decision areas

| Area (typical owner) | Decisions it supports | Questions (cookbook) | Confidence |
|---|---|---|---|
| **Governance coverage and quality** (head of governance, CDO) | Where to focus stewardship effort and campaigns; which KPIs to set | [How many Business Terms have a definition, per domain?](cookbook.md#6-how-many-business-terms-have-a-definition-per-domain); [Attribute completeness by asset type](cookbook.md#9-attribute-completeness-by-asset-type); [Where are Business Terms in the approval pipeline?](cookbook.md#7-where-are-business-terms-in-the-approval-pipeline); [Stale content: not edited for a year](cookbook.md#11-stale-content-not-edited-for-a-year); [Which assets share a name?](cookbook.md#8-which-assets-share-a-name) | High. Match attribute and status names to the client's operating model |
| **Accountability and risk** (DPO, risk, compliance) | Who to chase for missing ownership; what evidence to show an auditor | [Which Business Terms have no owner?](cookbook.md#10-which-business-terms-have-no-owner); [Which sensitive-tagged assets have no owner?](cookbook.md#30-which-sensitive-tagged-assets-have-no-owner); [Which responsibilities look like domain-level assignments?](cookbook.md#16-which-responsibilities-look-like-domain-level-assignments); [Who gained or lost responsibilities between two snapshots?](cookbook.md#26-who-gained-or-lost-responsibilities-between-two-snapshots) | Medium. Community-level ownership is invisible, direct and inherited rows look alike |
| **Adoption and engagement** (community managers, sponsors) | Where to train, what to retire, whether the platform is used | Without `view_events`: [Who creates the content?](cookbook.md#15-who-creates-the-content). With it: [How many people use Collibra each day?](cookbook.md#32-how-many-people-use-collibra-each-day); [Which assets are viewed most?](cookbook.md#33-which-assets-are-viewed-most); [Which content is never viewed?](cookbook.md#34-which-content-is-never-viewed) | Contribution is a proxy only. View data needs the optional table and counts UI events only |
| **Catalogue structure and operating-model health** (platform owner) | What to simplify, clean up or sunset | [What does the community tree look like?](cookbook.md#3-what-does-the-community-tree-look-like); [Which domains are empty?](cookbook.md#5-which-domains-are-empty); [Where does content live? (assets per community and domain)](cookbook.md#2-where-does-content-live-assets-per-community-and-domain); [Which attribute types are used most, and how are they typed?](cookbook.md#31-which-attribute-types-are-used-most-and-how-are-they-typed); [How many assets of each type and status?](cookbook.md#1-how-many-assets-of-each-type-and-status); [How many assets sit under each top-level community?](cookbook.md#4-how-many-assets-sit-under-each-top-level-community) | High |
| **Connectedness and impact** (architects, stewards) | What a change touches; which content is unlinked and should be connected | [Which assets have no relations at all?](cookbook.md#17-which-assets-have-no-relations-at-all); [Which assets are the most connected?](cookbook.md#18-which-assets-are-the-most-connected); [What is connected to this asset? (impact analysis, up to 3 hops)](cookbook.md#19-what-is-connected-to-this-asset-impact-analysis-up-to-3-hops); [How do asset types connect to each other?](cookbook.md#22-how-do-asset-types-connect-to-each-other); [Which Business Terms are linked to technical assets?](cookbook.md#20-which-business-terms-are-linked-to-technical-assets); [What do complex relations connect?](cookbook.md#21-what-do-complex-relations-connect) | Medium. Business relations only; relation types have no names in the export |
| **Progress over time** (sponsors, programme leads) | Whether governance is improving; whether targets are met | [Is definition coverage improving?](cookbook.md#28-is-definition-coverage-improving); [How did inventory change over time?](cookbook.md#23-how-did-inventory-change-over-time); [What was added between two snapshots?](cookbook.md#24-what-was-added-between-two-snapshots); [When was content created?](cookbook.md#27-when-was-content-created); [Which statuses changed between two snapshots?](cookbook.md#25-which-statuses-changed-between-two-snapshots) | High, but only once you hold several snapshots (start now: history cannot be recovered) |
| **Workload and access** (team leads) | Rebalancing stewardship; reviewing who holds what | [Who is responsible for how much?](cookbook.md#12-who-is-responsible-for-how-much); [Which groups hold responsibilities, and for what?](cookbook.md#14-which-groups-hold-responsibilities-and-for-what); [Which licence types hold responsibilities?](cookbook.md#13-which-licence-types-hold-responsibilities) | Medium. Only users with at least one responsibility appear; inherited rows inflate counts |

## 2. How the model answers them: six patterns

Almost every question above is one of six shapes over the [star schema](modeling.md):

| Pattern | Shape | Example |
|---|---|---|
| **Count by** | `dim_asset` grouped by type, status, domain or community | assets per domain |
| **Coverage (% with)** | `dim_asset` LEFT JOIN a *distinct* set from `fact_attribute` or `fact_responsibility`; count matched ÷ total | % of terms with a definition |
| **None of (gap)** | `NOT EXISTS` anti-join against a fact | terms without an owner, assets without relations |
| **Over time** | the same query with `snapshot_date` added to the `GROUP BY` and every join | coverage per month |
| **Connectedness** | `fact_relation`, testing both `asset_id1` and `asset_id2` (one direction is stored) | hubs, isolated assets, N-hop reach |
| **Who / how much** | `fact_responsibility` filtered to `asset_resolution = 'in_export'`, joined to `dim_user` | workload per person |

| Model object | Answers | Join key |
|---|---|---|
| `dim_asset` | what exists, its type, status, domain, community, creator | `(snapshot_date, asset_id)` |
| `dim_domain`, `dim_community`, `bridge_community_ancestor` | where it lives, the hierarchy | `(snapshot_date, domain_id / community_id)` |
| `fact_attribute` | how well it is described | `(snapshot_date, asset_id)` |
| `fact_relation`, `bridge_complex_relation` | how it is connected | `(snapshot_date, asset_id1 / asset_id2)` |
| `fact_responsibility`, `dim_user` | who is accountable | `(snapshot_date, asset_id)`, `(snapshot_date, user_id)` |
| `bridge_asset_tag` | classification (e.g. sensitivity) | `(snapshot_date, asset_id)` |
| `fact_view_event` *(optional)* | who looked at what | `asset_id`; its `snapshot_date` is the event date |
| `dim_snapshot` | the time axis | `snapshot_date` |

## 3. A starter scorecard

| KPI | Definition | Source |
|---|---|---|
| Definition coverage | Business Terms with a non-empty *Definition* ÷ all Business Terms | [How many Business Terms have a definition, per domain?](cookbook.md#6-how-many-business-terms-have-a-definition-per-domain) |
| Ownership coverage | Business Terms with an *Owner* ÷ all | [Which Business Terms have no owner?](cookbook.md#10-which-business-terms-have-no-owner) |
| Approved share | Terms in an *Approved* status ÷ all | [Where are Business Terms in the approval pipeline?](cookbook.md#7-where-are-business-terms-in-the-approval-pipeline) |
| Freshness | Assets edited in the last 12 months ÷ all | [Stale content: not edited for a year](cookbook.md#11-stale-content-not-edited-for-a-year); [Which assets share a name?](cookbook.md#8-which-assets-share-a-name) |
| Connectedness | Assets with at least one relation ÷ all | [Which assets have no relations at all?](cookbook.md#17-which-assets-have-no-relations-at-all) |
| Traceability | Business Terms linked to a technical asset ÷ all | [Which Business Terms are linked to technical assets?](cookbook.md#20-which-business-terms-are-linked-to-technical-assets) |
| Contributor concentration | Share of content created by the top 3 creators | [Who creates the content?](cookbook.md#15-who-creates-the-content) |
| Housekeeping | Non-system domains with no assets | [Which domains are empty?](cookbook.md#5-which-domains-are-empty) |
| Active users (if available) | Distinct users per day | [How many people use Collibra each day?](cookbook.md#32-how-many-people-use-collibra-each-day) |

Report each KPI per snapshot ([Is definition coverage improving?](cookbook.md#28-is-definition-coverage-improving) shows how) so the trend is the message, not the level.

## 4. What Insights cannot answer

Statements below follow from the table list ([data dictionary](data-dictionary.md)) and the documented limits; check them against your Collibra version.

| You may want… | Why Insights cannot give it | Look instead at |
|---|---|---|
| The quality of the data itself (rule results, profiling) | No such table among the eight (or `view_events`) | Collibra Data Quality & Observability |
| Technical lineage | No lineage table; only business relations between assets | Collibra Data Lineage |
| Workflow tasks, approval timestamps, per-attribute change history | Not in the tables; only snapshot-to-snapshot differences (daily for 31 days, then monthly) | Your own snapshot diffs; the activity APIs |
| Live state or "right now" | Nightly copy, processed in UTC | The REST API |
| Who is *not* using Collibra, or a user directory | No user table; users appear only through responsibilities and events | Usage Analytics; the users API |
| Usage | Needs the optional `view_events`; UI events only, since Usage Analytics was enabled | Usage Analytics dashboard |
| Ownership set on communities | Community-inherited responsibilities are excluded | The responsibilities API |
| Whether a responsibility is direct or inherited | No flag; a heuristic recipe exists | The responsibilities API |
| Which relation type a link is | Only ids and role labels | The relation-types API |

## 5. Serving these as data products

For a client that wants reporting tables or data products on a lakehouse, the scorecard-style questions above are materialised as gold tables: see [medallion.md](medallion.md).

## 6. Getting started with a client

Follow the [client playbook](client-playbook.md), then pick two or three rows of section 1 that match what the client cares about and run those recipes first.

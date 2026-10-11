# Approach: from Insights to decision-ready gold tables

**Purpose.** Insights is a daily photograph of a Collibra catalogue's metadata. This page says what can be modelled from it, which decisions a gold layer can support, and what to be upfront about. It is the summary; every statement links to the detail.

## 1. What you are modelling from

Eight tables (communities, domains, assets, attributes, tags, relations, complex relations, responsibilities), plus an optional ninth for Usage Analytics, delivered as a **full photo every night**. It describes the *catalogue* (what exists, who is responsible, how it is described and connected), not the data inside the client's systems, and it is never live. Detail: [overview](overview.md), [data dictionary](data-dictionary.md).

## 2. The modeling that is feasible

Three layers, kept deliberately simple:

| Layer | In one sentence | Why it exists |
|---|---|---|
| **Bronze** | Keep each photo exactly as delivered | Collibra only keeps 31 days of daily photos; this is how history survives |
| **Silver** | A small star schema: dimensions (community, domain, asset, user, date), facts (attribute values, relations, responsibilities, optional page views) | The raw tables have quirks (each relation stored twice, communities repeated per level, one long attribute list) that give wrong counts if queried directly |
| **Gold** | Additive counts per snapshot, per governed area, per asset type | One table per decision, so a report is a simple filter, not a join |

Detail and reasoning: [modeling guide](modeling.md). A concrete delivery option for the layers is in [medallion.md](medallion.md); it is optional, and the approach does not depend on it.

**What the data supports, and what it does not:**

| Feasible | Feasible with limits | Not feasible from Insights |
|---|---|---|
| Inventory by type, status, domain, community | Ownership: asset-level and domain-level are visible, **community-level is not**, and direct vs inherited cannot be told apart | Quality of the data itself (rule results, profiling) |
| Attribute coverage (definitions, descriptions, custom fields) | Relations: connectivity, traceability and impact work, but **relation types have no names** | Technical lineage |
| Connectedness and business-to-technical traceability | People: only those holding a responsibility appear; there is no user directory | Time-in-status, approval timestamps, per-attribute change history |
| **History** across snapshots: coverage trend, status moves, ownership churn, additions | Usage: needs the optional `view_events` table, which some tenants do not have; UI events only | Live state |

## 3. Decisions a gold layer can support

| Decision | Typical owner | Gold measure (additive) | Confidence |
|---|---|---|---|
| Where to focus stewardship effort | head of governance | governed assets, with a definition, with an owner, approved, stale, connected, per domain | High |
| Is governance improving, are targets met | sponsor | the same measures **per snapshot** | High, once history exists |
| Who is accountable for sensitive or critical content | risk, DPO | governed assets without an owner, filtered by tag | Medium (ownership limits above) |
| What to clean up or simplify | platform owner | assets by type, status, domain; stale assets; empty domains | High |
| What a change touches, is the catalogue linked to data | architect | assets with at least one relation, terms linked to technical assets | Medium |
| How to balance stewardship workload | team lead | assets and domains per role and person | Medium |
| Is the platform adopted | sponsor | active users and views per day *(only with `view_events`)*; otherwise contribution by creator as a weak proxy | Conditional |

The questions behind each row, with tested SQL: [use cases](use-cases.md) and [cookbook](cookbook.md).

## 4. Principles for the gold layer

1. **One gold table per decision**, and an owner for it. Start with two or three, not all.
2. **Additive counts, never ratios.** Compute a percentage in the BI tool as a sum over a sum, so any slice stays correct.
3. **Grain: snapshot × governed area × asset type.** Every table carries the snapshot date, so trends need no extra work.
4. **The client's names are configuration**, not logic: which attribute is "the definition", which role is "owner", which statuses mean "approved", which asset types are governed. Collect them first.
5. **Keep unmatched rows and label them.** A few rows always point at objects the export omits; dropping them silently makes totals wrong.
6. **Gate publication on a few must-be-zero checks**, not on every anomaly ([medallion §5](medallion.md#5-quality-gates-before-gold-is-published)).

## 5. Say this to the client upfront

* **The export is not identical to the UI.** Collibra has hidden built-in objects; the export includes some and omits others, so totals can differ from what users see. Reconcile once, early ([known gaps](known-gaps.md)).
* **Ownership is partly invisible** (community-level), and inherited rows look direct.
* **History starts the day you start collecting.** Nothing older than Collibra's retention can be recovered.
* **Usage questions depend on an optional table** that has to be confirmed with the client's Collibra administrator.
* **Personal data** (names, emails, usernames) sits in responsibilities and view events; model it minimally.

## 6. Suggested steps with a client

1. Confirm the Insights licence and set up an OAuth integration application for access.
2. Download one snapshot; reconcile it with the UI; list the client's real attribute, role, status and asset-type names ([playbook](client-playbook.md)).
3. Agree two or three decisions from section 3, each with a named owner.
4. Build silver once; build one gold table per agreed decision.
5. Start collecting history immediately, even before the gold tables are live.

# Approach: from Insights to decision-ready gold tables

**Purpose.** Insights is a daily photograph of a Collibra catalogue's metadata. This page says what can be modelled from it, which decisions a gold layer can support, and what to be upfront about. Every statement links to the detail.

## 1. What you are modelling from

Eight tables (communities, domains, assets, attributes, tags, relations, complex relations, responsibilities), plus an optional ninth for Usage Analytics, delivered as a **full photo every night**. It describes the *catalogue* (what exists, who is responsible, how it is described and connected), not the data inside the client's systems, and it is never live. Detail: [data dictionary](data-dictionary.md).

## 2. The modeling that is feasible

Three layers, kept deliberately simple:

| Layer | In one sentence | Why it exists |
|---|---|---|
| **Bronze** | Keep each photo exactly as delivered | Collibra only keeps 31 days of daily photos; this is how history survives |
| **Silver** | A small star schema: dimensions (community, domain, asset, user, date), facts (attribute values, relations, responsibilities, optional page views) | The raw tables have quirks (each relation stored twice, communities repeated per level, one long attribute list) that give wrong counts if queried directly |
| **Gold** | Additive counts per snapshot, per governed area, per asset type | One table per decision, so a report is a simple filter, not a join |

Detail and reasoning: [modeling guide](modeling.md).

**What the data supports, and what it does not:**

| Feasible | Feasible with limits | Not feasible from Insights |
|---|---|---|
| Inventory by type, status, domain, community | Ownership: asset-level and domain-level are visible, **community-level is not**, and direct vs inherited cannot be told apart | Profiling and full data-quality run history |
| Attribute coverage (definitions, descriptions, custom fields) | Relations: connectivity, traceability and impact work, but **relation types have no names** (the role label, e.g. *is part of*, is the best proxy) | The technical lineage graph |
| Connectedness and business-to-technical traceability | People: only those holding a responsibility appear; there is no user directory | Time-in-status, approval timestamps, per-attribute change history |
| **History** across snapshots: coverage trend, status moves, ownership churn, additions | Usage: needs the optional `view_events` table, which some tenants do not have; UI events only | Live state |
|  | Data quality: only what Collibra Data Quality writes back into the catalogue (rules, rule scores, dimensions as assets), as of each snapshot | |
|  | Lineage: only lineage-like relations stored in the catalogue (e.g. column *targets* column) | |

## 3. Decisions a gold layer can support

Each row names the questions behind it; the SQL is in the [cookbook](cookbook.md). Collibra's own prebuilt Insights reports (*Data Maturity*, *Privacy & Risk Readiness*, *Process Register*) map onto the first row and the privacy row: a good sign these are the decisions Insights was designed for. Which rows apply to a given client depends on the capabilities they use; `collibra-insights profile` shows that.

| Decision (typical owner) | Gold measure (additive) | Questions | Confidence |
|---|---|---|---|
| **Where to focus stewardship effort** (head of governance) | governed assets, with a definition, with an owner, approved, stale, connected, per domain | [How many Business Terms have a definition, per domain?](cookbook.md#6-how-many-business-terms-have-a-definition-per-domain); [Attribute completeness by asset type](cookbook.md#9-attribute-completeness-by-asset-type); [Where are Business Terms in the approval pipeline?](cookbook.md#7-where-are-business-terms-in-the-approval-pipeline); [Stale content: not edited for a year](cookbook.md#11-stale-content-not-edited-for-a-year); [Which assets share a name?](cookbook.md#8-which-assets-share-a-name) | High |
| **Is governance improving, are targets met** (sponsor) | the same measures **per snapshot** | [Is definition coverage improving?](cookbook.md#28-is-definition-coverage-improving); [How did inventory change over time?](cookbook.md#23-how-did-inventory-change-over-time); [What was added between two snapshots?](cookbook.md#24-what-was-added-between-two-snapshots); [Which statuses changed between two snapshots?](cookbook.md#25-which-statuses-changed-between-two-snapshots) | High, once history exists |
| **Who is accountable for sensitive or critical content** (risk, DPO) | governed assets without an owner, filtered by tag | [Which Business Terms have no owner?](cookbook.md#10-which-business-terms-have-no-owner); [Which sensitive-tagged assets have no owner?](cookbook.md#30-which-sensitive-tagged-assets-have-no-owner); [Which responsibilities look like domain-level assignments?](cookbook.md#16-which-responsibilities-look-like-domain-level-assignments) | Medium (ownership limits above) |
| **What to clean up or simplify** (platform owner) | assets by type, status, domain; stale assets; empty domains | [Which domains are empty?](cookbook.md#5-which-domains-are-empty); [What does the community tree look like?](cookbook.md#3-what-does-the-community-tree-look-like); [How many assets sit under each top-level community?](cookbook.md#4-how-many-assets-sit-under-each-top-level-community); [Which attribute types are used most, and how are they typed?](cookbook.md#31-which-attribute-types-are-used-most-and-how-are-they-typed) | High |
| **What a change touches, is the catalogue linked to data** (architect) | assets with at least one relation; terms linked to technical assets | [Which assets have no relations at all?](cookbook.md#17-which-assets-have-no-relations-at-all); [Which Business Terms are linked to technical assets?](cookbook.md#20-which-business-terms-are-linked-to-technical-assets); [What is connected to this asset? (impact analysis, up to 3 hops)](cookbook.md#19-what-is-connected-to-this-asset-impact-analysis-up-to-3-hops) | Medium |
| **How to balance stewardship workload** (team lead) | assets and domains per role and person | [Who is responsible for how much?](cookbook.md#12-who-is-responsible-for-how-much); [Which groups hold responsibilities, and for what?](cookbook.md#14-which-groups-hold-responsibilities-and-for-what); [Who gained or lost responsibilities between two snapshots?](cookbook.md#26-who-gained-or-lost-responsibilities-between-two-snapshots) | Medium |
| **Are we ready for a regulation, is the processing register complete** (privacy office, DPO) | business processes per process register, with linked data sets and third parties; completeness of their required attributes | Collibra ships prebuilt *Privacy & Risk Readiness* and *Process Register* reports for this | Conditional: only if the client uses Collibra's privacy features (`profile` shows a *Privacy & risk* capability) |
| **Is the platform adopted** (sponsor) | active users and views per day *(only with `view_events`)*; otherwise contribution by creator as a weak proxy | [Who creates the content?](cookbook.md#15-who-creates-the-content); with `view_events`: [How many people use Collibra each day?](cookbook.md#32-how-many-people-use-collibra-each-day), [Which assets are viewed most?](cookbook.md#33-which-assets-are-viewed-most), [Which content is never viewed?](cookbook.md#34-which-content-is-never-viewed) | Conditional |

**A starter scorecard** (report each per snapshot, so the trend is the message):

| KPI | Definition | Recipe |
|---|---|---|
| Definition coverage | Business Terms with a non-empty definition ÷ all Business Terms | [How many Business Terms have a definition, per domain?](cookbook.md#6-how-many-business-terms-have-a-definition-per-domain) |
| Ownership coverage | Business Terms with an owner ÷ all | [Which Business Terms have no owner?](cookbook.md#10-which-business-terms-have-no-owner) |
| Approved share | Terms in an approved status ÷ all (statuses differ per workflow: list them per asset type first) | [Where are Business Terms in the approval pipeline?](cookbook.md#7-where-are-business-terms-in-the-approval-pipeline) |
| Freshness | Assets edited in the last 12 months ÷ all | [Stale content: not edited for a year](cookbook.md#11-stale-content-not-edited-for-a-year) |
| Connectedness | Assets with at least one relation ÷ all | [Which assets have no relations at all?](cookbook.md#17-which-assets-have-no-relations-at-all) |
| Traceability | Business Terms linked to a technical asset ÷ all | [Which Business Terms are linked to technical assets?](cookbook.md#20-which-business-terms-are-linked-to-technical-assets) |
| Contributor concentration | Share of content created by the top 3 creators | [Who creates the content?](cookbook.md#15-who-creates-the-content) |
| Housekeeping | Non-system domains with no assets | [Which domains are empty?](cookbook.md#5-which-domains-are-empty) |

## 4. Principles for the gold layer

1. **One gold table per decision**, and an owner for it. Start with two or three, not all.
2. **Additive counts, never ratios.** Compute a percentage in the BI tool as a sum over a sum, so any slice stays correct.
3. **Grain: snapshot × governed area × asset type.** Every table carries the snapshot date, so trends need no extra work.
4. **The client's names are configuration**, not logic: which attribute is "the definition", which role is "owner", which statuses mean "approved", which asset types are governed. Collect them first.
5. **Keep unmatched rows and label them.** A few rows always point at objects the export omits; dropping them silently makes totals wrong.
6. **Scope before you count.** A large share of an export is not business content, and counting it distorts every KPI. Before computing anything, remove or separate:
   * **Collibra's own configuration**, exported as assets in *Operating Model Dictionary* domains (Domain, Community, Attribute Type, Relation Type, Assignment, Permission…), with their relations and complex relations;
   * assets in a **terminal status** (*Removed*, *Missing from source*…);
   * **harvested** technical attributes (data type, nullable, position, created-on…) when measuring *curated* documentation;
   * **structural** relations (*is part of*, *contains*, *is of type*) when measuring business connectedness or traceability.

   `collibra-insights profile` measures each of these for a client (section *scope*).
7. **Gate publication on a few must-be-zero checks**, not on every anomaly. Run `collibra-insights check` and gate like this:

| Check (from `check`) | Gate |
|---|---|
| attribute, tag or relation pointing at a missing asset; relations not stored twice; duplicate asset or community keys; community parent mismatch | **must be 0**: block publication |
| asset missing its domain; domain missing its community; responsibility missing its asset | normal (hidden built-in objects); alert only on a large jump versus the previous snapshot |
| row counts per table | alert beyond a threshold (say 20%) versus the previous snapshot |

## 5. Say this to the client upfront

* **The export is not identical to the UI.** Collibra has hidden built-in objects; the export includes some and omits others, so totals can differ from what users see. Reconcile once, early ([known gaps](known-gaps.md)).
* **Ownership is partly invisible** (community-level), and inherited rows look direct.
* **History starts the day you start collecting.** Nothing older than Collibra's retention can be recovered.
* **Usage questions depend on an optional table** that has to be confirmed with the client's Collibra administrator.
* **Vocabularies are local and often messy.** Statuses differ per workflow and include ad-hoc values; classification (personal data, confidentiality) may live in **attributes rather than tags**, sometimes duplicated across languages or teams. Agree the client's definitions of "approved", "owned" and "sensitive" before computing anything.
* **Most of the volume is harvested, not curated.** Integrations create columns, code values and their technical attributes in bulk; human documentation is a much smaller share. Coverage KPIs must say which one they measure.
* **Personal data** (names, emails, usernames) sits in responsibilities and view events; model it minimally.

## 6. Suggested steps with a client

1. Confirm the Insights licence and set up an OAuth integration application for access.
2. Download one snapshot and run `profile`: it shows which capabilities the client actually uses (so which rows of section 3 apply) and their real attribute, role, status and asset-type names. Reconcile the totals with the UI ([playbook](client-playbook.md)).
3. Agree two or three decisions from section 3, each with a named owner.
4. Build silver once; build one gold table per agreed decision.
5. Start collecting history immediately, even before the gold tables are live.

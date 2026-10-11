# Modelling Insights data

> **Status:** conceptual. The shape below follows from the *documented* tables and how Collibra's operating model works. Column names are deliberately left as `<...>` until we've inspected a real snapshot (`collibra-insights explore`). Treat every `<...>` as a TODO to confirm, not a fact.

## 1. Read the raw tables as an operating-model graph

```
community 1──* domain 1──* asset ──* attribute        (values: definition, description, custom)
                             │ ──* asset_tag
                             │ ──* responsibility     (owner / stakeholder on a resource)
                             ├──* relation            (asset ↔ asset, typed)
                             └──* complex_relation    (n-ary, typed)
usage view events ──> (user, resource visited, time)
```

Collibra stores *content* generically: one `attribute` table for every kind of attribute, one `relation` table for every kind of link. That's flexible for Collibra but awkward for BI. This is the classic **entity-attribute-value (EAV)** shape.

## 2. Target: a small star schema

| Layer | Table | Grain (one row per…) | Built from |
|---|---|---|---|
| Dimension | `dim_community` | community | `community` |
| Dimension | `dim_domain` | domain (carries its community) | `domain` + community |
| Dimension | `dim_asset` | asset, with domain/community/type denormalised | `asset` + `dim_domain` |
| Dimension | `dim_date` | calendar day | generated |
| Fact | `fact_attribute` | asset × attribute type × snapshot | `attribute` |
| Fact | `fact_relation` | relation instance × snapshot | `relation` |
| Fact | `fact_responsibility` | resource × role × party × snapshot | `responsibility` |
| Fact | `fact_view_event` | page view | usage analytics |
| Bridge | `bridge_asset_tag` | asset × tag | `asset_tag` |

Why a star? BI questions ("how many Business Terms per domain, owned by whom, with/without a definition?") become one join from a fact to a few small dimensions.

## 3. Three decisions that matter

**a) Snapshots are the time axis.** Every record carries the date the data was copied. Store `snapshot_date` as a key into `dim_date`, keep the daily/monthly/yearly snapshots you load, and you get history (e.g. "definition coverage by month") for free. Without it you only ever see "now". Decide whether you load *all* retained snapshots or only month-ends; month-ends are enough for trends and far smaller.

**b) Pivot attributes, per asset type, not globally.** `fact_attribute` is long; analysts want `Business Term` as one row with `definition`, `status`, `steward` as columns. Build a *wide view per asset type you care about* (`mart_business_term`, `mart_column`, …) by pivoting selected attribute types. Don't pivot everything: custom attribute types vary per environment and a global pivot gets unmanageably wide and unstable.

**c) Relations are directed and typed; model both directions deliberately.** "categorizes" and "is categorized by" are the same link read from each end. Pick one canonical direction per relation type in `fact_relation` (store source asset, target asset, relation type) and expose the reverse as a view if needed, otherwise counts double.

## 4. Conformance checks to run on every load

1. Every `asset.domain` exists in `domain`; every `domain.community` in `community` (orphans mean partial export).
2. Attribute/relation rows reference existing assets.
3. Row counts per table are within tolerance of the previous snapshot.
4. Excluded types (Roles, Workflow Definitions) do **not** appear: if they do, our assumption about the export is wrong.

## 5. Next step: fill in the `<...>`

1. Download one snapshot, run `collibra-insights explore`.
2. Paste column lists into a new `docs/schema-observed.md`.
3. Write the DuckDB `CREATE VIEW` SQL for each dimension/fact in `sql/`.
4. Add the checks from §4 as tests.

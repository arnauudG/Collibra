# Modelling Insights data

> **Status:** columns below are **observed** from a real snapshot (2026-10-10, a training instance). How the tables behave (grain, duplicates, hierarchy shape) is partly **inferred from column names** and marked *to verify*; the queries in §5 settle each one.

## 1. What a snapshot contains (observed)

Eight tables. Every table has `snapshot_date` (DATE) plus `snapshot_date_year/month/day` (the Hive partition columns), `creator_*` / `editor_*` audit columns, and VARCHAR ids. No Usage Analytics table was present in this snapshot (reason unknown).

| Table | Rows | Key columns |
|---|---|---|
| `community` | 357 | `community_id`, `community_name`, `parent_community_id`, `level`, `level_community_id/name/uri` |
| `domain` | 585 | `domain_id`, `domain_name`, `domain_type_id/name`, `community_id` |
| `asset` | 23,202 | `asset_id`, `asset_full_name`, `asset_display_name`, `domain_id`, `asset_type_id/name`, `status_id/name`, `articulation`, `ratings_average/count` |
| `asset_tag` | 147 | `tag_id`, `asset_id`, `tag_name` |
| `attribute` | 116,935 | `attribute_id`, `asset_id`, `asset_type_name`, `attribute_type_id/name`, `kind`, value columns (below), `complex_relation_id` |
| `relation` | 54,720 | `relation_id`, `relation_type_id`, `role_or_corole`, `direction`, `asset_id1/2`, `asset_type_id1/2`, `asset_type_name1/2`, `is_relation_generated` |
| `complex_relation` | 9,710 | `complex_relation_id`, `complex_relation_type_id/name`, `relation_type_id`, `relation_role`, `asset_id` |
| `responsibility` | 20,036 | `role_id`, `role_name`, `asset_id`, `user_id`, `username`, `user_*` (name, email, licence, flags), `group_id`, `group_name` |

Full column lists: run `collibra-insights explore <snapshot>`.

## 2. How the tables join

```
community ──< domain ──< asset ──< attribute          (asset_id)
 (community_id)  (domain_id)  │ ──< asset_tag         (asset_id)
                              │ ──< responsibility    (asset_id; user_id or group_id)
                              ├──  relation           (asset_id1 ↔ asset_id2)
                              └──< complex_relation   (asset_id, per participant)
attribute.complex_relation_id ──> complex_relation    (attributes that sit on a complex relation)
```

Names are already denormalised in places (`asset_type_name` in `attribute` and `relation`, `domain_type_name` in `domain`), which saves joins.

## 3. Target: a small star schema

| Layer | Table | Grain | Built from |
|---|---|---|---|
| Dim | `dim_community` | community | `community` (see hierarchy note) |
| Dim | `dim_domain` | domain, with its community | `domain` ⨝ `community` |
| Dim | `dim_asset` | asset, with domain / community / type / status | `asset` ⨝ `dim_domain` |
| Dim | `dim_user` | user (derived) | distinct user columns of `responsibility` |
| Dim | `dim_date` | day | generated |
| Fact | `fact_attribute` | attribute instance × snapshot | `attribute` |
| Fact | `fact_relation` | relation × snapshot | `relation` |
| Fact | `fact_responsibility` | asset × role × user/group × snapshot | `responsibility` |
| Bridge | `bridge_asset_tag` | asset × tag | `asset_tag` |

There is no standalone user table: users only appear inside `responsibility`, so `dim_user` has to be derived. Those columns include names and emails; decide up front whether to keep or hash them.

## 4. Decisions that matter

**a) Snapshots are the time axis.** Keep `snapshot_date` on every fact and join to `dim_date`. Loading month-end snapshots gives trends cheaply; daily gives detail for the last 31 days.

**b) Attributes are typed EAV.** One row per attribute with the value in one of: `expression_long` (text), `boolean_value`, `datetime_value`, `numeric_value`, discriminated by `kind` (observed: STRING, NUMERIC, BOOLEAN, MULTI_VALUE_LIST, SINGLE_VALUE_LIST, DATE, SCRIPT). Which `kind` fills which column is **not verified**, so `fact_attribute.value_as_text` coalesces all four columns instead of assuming. Keep `fact_attribute` long, and pivot only chosen attribute types into wide marts per asset type (`mart_business_term`: definition, description, …). A global pivot is unstable because custom attribute types differ per environment.

**c) Every relation is stored twice (verified).** In the 2026-10-10 snapshot each `relation_id` has exactly two rows, `direction = 'head -> tail'` and `'tail -> head'` (27,360 ids, 54,720 rows). So `count(*)` over `relation` doubles everything. Build `fact_relation` with **one row per `relation_id`** by keeping `direction = 'head -> tail'`, and expose the reverse reading as a view if needed. The two rows are exact mirrors (`asset_id1`/`asset_id2` swapped): 27,360 of 27,360 verified.

**d) Complex relations are one row per participant** (`relation_role` + `asset_id` under a `complex_relation_id`; 9,710 rows / 4,823 ids, about 2 each). Model as a bridge keyed by `complex_relation_id`.

**e) Community hierarchy is pre-flattened.** `level` and `level_community_*` give one row per community × level, so `community_id` repeats (357 rows / 187 ids, verified). `dim_community` keeps one row per `community_id`. An ancestors bridge is **not built yet**: what `level` means exactly (the community's own depth vs. the ancestor's) still needs checking.

## 5. Checks run so far, and still open

Verified on 2026-10-10: relation mirrored; complex_relation and community repeat ids; **14 assets reference a domain missing from the export** (kept in `dim_asset` with `is_domain_missing = true`; cause unknown). The 14 orphan assets are all type *Issue Category*, and the one domain without a community is of type *Issues Vocabulary Type*: the gaps cluster around Collibra's Issues content (possibly the docs' excluded-types rule; unverified). 5,027 responsibilities point at ids that are not an asset, domain or community (unexplained). Still open: `kind` → value column mapping, meaning of `community.level`.

Reproduce:

```bash
S=snapshots/insights-2026-10-10
collibra-insights query $S "select direction, count(*) from relation group by 1"
collibra-insights query $S "select count(*) rows_, count(distinct relation_id) ids from relation"   # verified: 54720 / 27360
collibra-insights query $S "select count(*) mirrored from relation a join relation b on a.relation_id=b.relation_id and a.direction='head -> tail' and b.direction='tail -> head' and a.asset_id1=b.asset_id2 and a.asset_id2=b.asset_id1"   # expect 27360
collibra-insights query $S "select count(*) rows_, count(distinct complex_relation_id) ids from complex_relation"
collibra-insights query $S "select count(*) rows_, count(distinct community_id) ids from community"
collibra-insights query $S "select kind, count(*) from attribute group by 1 order by 2 desc"
collibra-insights query $S "select count(*) orphans from asset a left join domain d using(domain_id) where d.domain_id is null"
```
These are aggregates only (no names or emails).

## 6. The model in code

`collibra_insights.model.build_model(snapshot)` creates `dim_community`, `dim_domain`, `dim_asset`, `dim_user`, `dim_snapshot`, `fact_attribute`, `fact_relation`, `fact_responsibility`, `bridge_asset_tag`, `bridge_complex_relation`. `dim_user` omits first name, last name and email unless `include_pii=True`. CLI: `collibra-insights query <snapshot> "select ..." --model`.

## 7. Conformance checks (`collibra-insights check <snapshot>`)

1. No orphan assets (`asset.domain_id` ∈ `domain`), domains (`community_id` ∈ `community`).
2. `attribute`, `relation`, `asset_tag` only reference existing `asset_id`s. `responsibility_missing_asset` is nonzero on the real snapshot (5,027 of 20,036) and **not** explained by domains or communities (checked: none of those ids match a domain or community). Treat it as an open data-quality question.
3. Row counts within tolerance of the previous snapshot.
4. Excluded types (Roles, Workflow Definitions) are absent.

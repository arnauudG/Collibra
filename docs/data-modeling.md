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

**b) Attributes are typed EAV (verified).** One row per attribute. `expression_long` holds a text rendering for essentially every kind; the typed column adds the real value: NUMERIC → `numeric_value`, BOOLEAN → `boolean_value`, DATE → `datetime_value`. STRING, SINGLE/MULTI_VALUE_LIST and SCRIPT use `expression_long` only (counts on 2026-10-10: STRING 69,313; NUMERIC 24,579; BOOLEAN 19,880; MULTI_VALUE_LIST 1,603; SINGLE_VALUE_LIST 1,275; DATE 284; SCRIPT 1). A few rows have a typed value but no text (56 NUMERIC) or an empty text (34 STRING), so `fact_attribute.value_as_text` coalesces all four columns. Keep `fact_attribute` long, and pivot only chosen attribute types into wide marts per asset type. *Not yet checked:* how multi-value lists are encoded inside `expression_long`.

**c) Every relation is stored twice (verified).** In the 2026-10-10 snapshot each `relation_id` has exactly two rows, `direction = 'head -> tail'` and `'tail -> head'` (27,360 ids, 54,720 rows). So `count(*)` over `relation` doubles everything. Build `fact_relation` with **one row per `relation_id`** by keeping `direction = 'head -> tail'`, and expose the reverse reading as a view if needed. The two rows are exact mirrors (`asset_id1`/`asset_id2` swapped): 27,360 of 27,360 verified.

**d) Complex relations are one row per participant** (`relation_role` + `asset_id` under a `complex_relation_id`; 9,710 rows / 4,823 ids, about 2 each). Model as a bridge keyed by `complex_relation_id`.

**e) Community hierarchy is a root-to-self path per community (verified).** A community at depth *d* has exactly *d* rows, `level` 1..*d*, where `level_community_id` is the ancestor at that level and level *d* is the community itself (187 of 187 communities satisfy this; 62 roots; deepest = 4). `dim_community` therefore has one row per community with `depth` and `is_root`, and `bridge_community_ancestor` lists every ancestor. The `community_parent_mismatch` check tests that level *d−1* equals `parent_community_id`.

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

## 8. What we know about gaps (export vs. live instance, 2026-10-10)

Evidence from `collibra-insights investigate --live`. Confidence is stated per finding.

| Finding | Evidence | Confidence |
|---|---|---|
| Export is a **superset** of what the REST list endpoints return | assets: export 23,202 vs live 23,099 (**+103** = 101 *Data Usage* + 2 *Data Issue*, types the live list reports as 0); domains: export 585 vs live 398 (**+187** = the 187 *Issues Vocabulary Type* domains); communities equal (187) | High for the counts. Why the live list hides them is **unverified** (a default filter such as hidden/meta is likely) |
| Nothing visible in the live list is missing from the export (by count) | the +103 / +187 differences are fully explained by the hidden types above | Medium: equal totals do not prove identical members |
| The 14 orphan assets sit in a built-in **Issue Classification** domain that exists live but is absent from the export's `domain` table; the 1 orphan domain sits in a community (id `00000000…`) that exists live but is absent from the export | live lookups of those ids succeed; the ids use the system-style `00000000-` prefix | High that they exist and are built-in; the exclusion rule itself is unverified |
| 5,027 unresolved responsibilities are limited to **3 roles** (Community Manager 4,904, Data Quality Manager 122, Data Quality Viewer 1), and every row of those roles is unresolved | role breakdown | High |
| Their ids are almost one per row (5,026 ids / 5,027 rows), so they are not shared resources | counts | High |
| Some of them are `Role Type` assets, an excluded type per Collibra's docs | live lookup of the 8 *lowest* ids only | **Low**: biased sample. The spread sample in `investigate --live` is meant to settle it |
| No Usage Analytics table | only `.parquet` files, 8 top-level folders | High that it is absent; cause unknown |

Practical rule: **`LEFT JOIN` from facts to dimensions and keep unmatched rows**, since a few rows legitimately point at built-in objects the export omits.

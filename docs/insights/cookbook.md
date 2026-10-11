# Cookbook: questions you can answer with Insights

Each recipe is a business question, a query on the [model](modeling.md), and the traps to avoid. Every query in this file is executed by the test suite against a fixture, so none should fail on a bind or syntax error. They have **not** all been run on real data, so sanity-check numbers before presenting them.

## How to run a recipe

1. Download a snapshot: `collibra-insights download 2026-10-10` (first time at a client? follow the [playbook](client-playbook.md))
2. Put the SQL in a file (say `q.sql`) and run:
   ```bash
   collibra-insights query snapshots/insights-2026-10-10 --model --file q.sql
   ```
   `--model` creates the views used below (`dim_asset`, `fact_attribute`…).
3. Or use Python: `s = Snapshot(path); build_model(s); s.sql("…").fetchall()`.

**One snapshot or many?** The recipes assume **one** snapshot is loaded. If you point at a parent folder holding several snapshots (for trends), every query would count each snapshot's rows. Add `WHERE snapshot_date = (SELECT max(snapshot_date) FROM dim_snapshot)` (or filter in each join), or use recipes 14-15, which are written for several snapshots.

**Personal data:** `dim_user` keeps usernames but not names or emails unless you build the model with `include_pii=True`.

---

## Inventory

### 1. How many assets of each type and status?
```sql
SELECT asset_type_name, status_name, count(*) AS assets
FROM dim_asset
GROUP BY 1, 2
ORDER BY 3 DESC
```
*Watch out:* includes the hidden meta types the export carries (*Data Usage*, *Data Issue*); see [known-gaps](known-gaps.md).

### 2. Where does content live? (assets per community and domain)
```sql
SELECT community_name, domain_name, domain_type_name, count(*) AS assets
FROM dim_asset
GROUP BY 1, 2, 3
ORDER BY 4 DESC
LIMIT 25
```
*Watch out:* assets whose domain is missing from the export have null names here (`is_domain_missing`).

### 3. What does the community tree look like?
```sql
SELECT c.community_name, c.depth,
       string_agg(b.ancestor_name, ' > ' ORDER BY b.ancestor_level) AS path
FROM dim_community c
JOIN bridge_community_ancestor b USING (snapshot_date, community_id)
GROUP BY c.snapshot_date, c.community_id, c.community_name, c.depth
ORDER BY path
```
*Reads as:* one line per community with its root-to-self path. Needs `bridge_community_ancestor` because the raw table repeats each community once per level.

---

## Data quality and completeness

### 4. How many Business Terms have a definition, per domain?
```sql
SELECT a.domain_name,
       count(*) AS terms,
       count(d.asset_id) AS with_definition,
       round(100.0 * count(d.asset_id) / count(*), 1) AS pct_defined
FROM dim_asset a
LEFT JOIN (
    SELECT DISTINCT snapshot_date, asset_id
    FROM fact_attribute
    WHERE attribute_type_name = 'Definition' AND coalesce(value_as_text, '') <> ''
) d ON d.snapshot_date = a.snapshot_date AND d.asset_id = a.asset_id
WHERE a.asset_type_name = 'Business Term'
GROUP BY 1
ORDER BY terms DESC
```
*Watch out:* the attribute type is matched **by name** (`'Definition'`); spelling and language depend on your operating model. Check `SELECT DISTINCT attribute_type_name FROM fact_attribute`.

### 5. Attribute completeness by asset type
```sql
WITH n AS (
    SELECT snapshot_date, asset_type_name, count(*) AS assets
    FROM dim_asset GROUP BY 1, 2
),
f AS (
    SELECT a.snapshot_date, a.asset_type_name, t.attribute_type_name,
           count(DISTINCT t.asset_id) AS with_attr
    FROM fact_attribute t
    JOIN dim_asset a ON a.snapshot_date = t.snapshot_date AND a.asset_id = t.asset_id
    WHERE coalesce(t.value_as_text, '') <> ''
    GROUP BY 1, 2, 3
)
SELECT f.asset_type_name, f.attribute_type_name, f.with_attr, n.assets,
       round(100.0 * f.with_attr / n.assets, 1) AS pct_filled
FROM f JOIN n ON n.snapshot_date = f.snapshot_date AND n.asset_type_name = f.asset_type_name
ORDER BY f.asset_type_name, pct_filled DESC
```
*Reads as:* for each asset type, how often each attribute is filled in. Attributes that are never filled for a type do not appear at all.

### 6. Which Business Terms have no owner?
```sql
SELECT a.domain_name, count(*) AS terms_without_owner
FROM dim_asset a
WHERE a.asset_type_name = 'Business Term'
  AND NOT EXISTS (
      SELECT 1 FROM fact_responsibility r
      WHERE r.snapshot_date = a.snapshot_date
        AND r.asset_id = a.asset_id
        AND r.role_name = 'Owner')
GROUP BY 1
ORDER BY 2 DESC
```
*Watch out:* the export includes asset-level responsibilities and those **inherited from domains**, but **not those inherited from communities**. If owners are assigned at community level, this **overstates** the gap. Role names are matched by text (`'Owner'`); list yours with `SELECT DISTINCT role_name FROM fact_responsibility`.

### 7. Stale content: not edited for a year
```sql
SELECT domain_name, asset_type_name, count(*) AS stale_assets
FROM dim_asset
WHERE edited_date < snapshot_date - INTERVAL 365 DAY
GROUP BY 1, 2
ORDER BY 3 DESC
```
*Watch out:* `edited_date` changes on any edit, including bulk imports.

---

## People and responsibilities

### 8. Who is responsible for how much?
```sql
SELECT u.username, r.role_name, count(*) AS assets
FROM fact_responsibility r
JOIN dim_user u ON u.snapshot_date = r.snapshot_date AND u.user_id = r.user_id
WHERE r.asset_resolution = 'in_export'
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 25
```
*Watch out:* the `in_export` filter removes ~5,000 rows pointing at hidden meta assets; without it one user appears to manage thousands of assets. Group-held responsibilities (`group_id`) are not included.

### 9. Which licence types hold responsibilities?
```sql
SELECT user_licensetype, is_user_enabled, count(*) AS users
FROM dim_user
GROUP BY 1, 2
ORDER BY 3 DESC
```
*Watch out:* **only users with at least one responsibility** exist in the export. This is not a licence inventory.

### 10. Which groups hold responsibilities, and for what?
```sql
SELECT group_name, role_name, count(*) AS assets
FROM fact_responsibility
WHERE group_id IS NOT NULL AND asset_resolution = 'in_export'
GROUP BY 1, 2
ORDER BY 3 DESC
```

---

## Relationships and lineage-style questions

### 11. Which assets have no relations at all?
```sql
SELECT a.asset_type_name, count(*) AS isolated_assets
FROM dim_asset a
WHERE NOT EXISTS (
    SELECT 1 FROM fact_relation r
    WHERE r.snapshot_date = a.snapshot_date
      AND (r.asset_id1 = a.asset_id OR r.asset_id2 = a.asset_id))
GROUP BY 1
ORDER BY 2 DESC
```
*Reads as:* content that is not connected to anything, a typical governance smell. `fact_relation` keeps one direction per relationship, so the `OR` over both ends is what makes this correct.

### 12. Which assets are the most connected?
```sql
WITH ends AS (
    SELECT snapshot_date, asset_id1 AS asset_id FROM fact_relation
    UNION ALL
    SELECT snapshot_date, asset_id2 FROM fact_relation
)
SELECT a.asset_display_name, a.asset_type_name, count(*) AS relations
FROM ends e
JOIN dim_asset a ON a.snapshot_date = e.snapshot_date AND a.asset_id = e.asset_id
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 20
```

### 13. How do asset types connect to each other?
```sql
SELECT asset_type_name1 AS from_type, asset_type_name2 AS to_type,
       role_or_corole, count(*) AS relations
FROM fact_relation
GROUP BY 1, 2, 3
ORDER BY 4 DESC
```
*Watch out:* relation **type names are not in the export**, only the role label; two different relation types between the same asset types can look alike.

---

## History and trends (load several snapshots)

Put several snapshots under one parent folder (`snapshots/insights-2026-10-09`, `…-10`) and point `--model` at the parent. The date literals below are examples; change them.

### 14. How did inventory change over time?
```sql
SELECT snapshot_date, asset_type_name, count(*) AS assets
FROM dim_asset
GROUP BY 1, 2
ORDER BY 1, 3 DESC
```

### 15. What was added between two snapshots?
```sql
SELECT b.asset_type_name, count(*) AS new_assets
FROM dim_asset b
WHERE b.snapshot_date = DATE '2026-10-10'
  AND NOT EXISTS (
      SELECT 1 FROM dim_asset a
      WHERE a.snapshot_date = DATE '2026-10-09' AND a.asset_id = b.asset_id)
GROUP BY 1
ORDER BY 2 DESC
```
*Reads as:* assets present on the later date and absent on the earlier one. Swap the dates to see what was removed.

### 16. When was content created?
```sql
SELECT date_trunc('month', CAST(creation_date AS TIMESTAMP)) AS month, asset_type_name, count(*) AS created
FROM dim_asset
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
```
*Watch out:* a bulk import shows up as one huge month.

---

## Tags and attributes

### 17. Which tags are used most?
```sql
SELECT tag_name, count(DISTINCT asset_id) AS assets
FROM bridge_asset_tag
GROUP BY 1
ORDER BY 2 DESC
```

### 18. Which attribute types are used most, and how are they typed?
```sql
SELECT attribute_type_name, kind, count(*) AS values_, count(DISTINCT asset_id) AS assets
FROM fact_attribute
GROUP BY 1, 2
ORDER BY 3 DESC
```

---

## Usage Analytics (needs the optional `view_events` table)

These recipes only run if your snapshots contain `view_events` (check with `collibra-insights tables-available`). Only **user-interface** events are counted, usernames are personal data, and `snapshot_date` in this table is the day the event happened. The columns come from Collibra's documentation; they were not available on the reference instance to verify.

### 19. How many people use Collibra each day?
```sql
SELECT snapshot_date AS day, count(DISTINCT user_id) AS active_users, count(*) AS views
FROM fact_view_event
GROUP BY 1
ORDER BY 1
```

### 20. Which assets are viewed most?
```sql
SELECT a.asset_display_name, a.asset_type_name,
       count(*) AS views, count(DISTINCT v.user_id) AS viewers
FROM fact_view_event v
JOIN dim_asset a
  ON a.asset_id = CAST(v.asset_id AS VARCHAR)
 AND a.snapshot_date = (SELECT max(snapshot_date) FROM dim_snapshot)
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 20
```
*Reads as:* the content people actually read. Events on diagrams, dashboards or pages other than assets have no `asset_id` and are not counted here.

### 21. Which content is never viewed?
```sql
SELECT a.asset_type_name, count(*) AS never_viewed
FROM dim_asset a
WHERE a.snapshot_date = (SELECT max(snapshot_date) FROM dim_snapshot)
  AND NOT EXISTS (
      SELECT 1 FROM fact_view_event v
      WHERE CAST(v.asset_id AS VARCHAR) = a.asset_id)
GROUP BY 1
ORDER BY 2 DESC
```
*Watch out:* "never viewed" covers only the period the events span; API and Edge access is invisible.

---

## Checking the data itself

Run `collibra-insights check <snapshot>` after every download. It reports orphans, duplicate keys and relations that are not stored twice. Known, expected non-zero results are listed in [known-gaps.md](known-gaps.md).

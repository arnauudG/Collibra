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

**One snapshot or many?** The recipes assume **one** snapshot is loaded. If you point at a parent folder holding several snapshots (for trends), every query would count each snapshot's rows. Add `WHERE snapshot_date = (SELECT max(snapshot_date) FROM dim_snapshot)` (or filter in each join), or use the *History and trends* recipes, which are written for several snapshots.

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

### 4. Which domains are empty?
```sql
SELECT d.domain_type_name, d.is_domain_system, count(*) AS empty_domains
FROM dim_domain d
WHERE NOT EXISTS (
    SELECT 1 FROM dim_asset a
    WHERE a.snapshot_date = d.snapshot_date AND a.domain_id = d.domain_id)
GROUP BY 1, 2
ORDER BY 3 DESC
```
*Reads as:* housekeeping candidates. Built-in domains (`is_domain_system`) are normally empty and should be ignored; empty non-system domains are clean-up or onboarding candidates.

### 5. How many Business Terms have a definition, per domain?
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

### 6. Where are Business Terms in the approval pipeline?
```sql
SELECT domain_name, status_name, count(*) AS terms
FROM dim_asset
WHERE asset_type_name = 'Business Term'
GROUP BY 1, 2
ORDER BY 1, 3 DESC
```
*Reads as:* the status mix per domain, e.g. how many terms are still *Candidate* versus *Approved*. Status names are your workflow's; list them with `SELECT DISTINCT status_name FROM dim_asset`.

### 7. Attribute completeness by asset type
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

### 8. Which Business Terms have no owner?
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

### 9. Stale content: not edited for a year
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

### 10. Who is responsible for how much?
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

### 11. Which licence types hold responsibilities?
```sql
SELECT user_licensetype, is_user_enabled, count(*) AS users
FROM dim_user
GROUP BY 1, 2
ORDER BY 3 DESC
```
*Watch out:* **only users with at least one responsibility** exist in the export. This is not a licence inventory.

### 12. Which groups hold responsibilities, and for what?
```sql
SELECT group_name, role_name, count(*) AS assets
FROM fact_responsibility
WHERE group_id IS NOT NULL AND asset_resolution = 'in_export'
GROUP BY 1, 2
ORDER BY 3 DESC
```

### 13. Who creates the content?
```sql
WITH per AS (
    SELECT creator_username, count(*) AS created
    FROM dim_asset
    WHERE creator_username IS NOT NULL
    GROUP BY 1
)
SELECT creator_username, created,
       round(100.0 * created / sum(created) OVER (), 1) AS pct_of_all_created
FROM per
ORDER BY created DESC
LIMIT 20
```
*Reads as:* contribution concentration. If three people created most of the catalogue, that is a continuity risk. It is also the best **adoption proxy when `view_events` is absent**.
*Watch out:* integration and API users create content in bulk and will top the list; judge them separately. Usernames are personal data.

### 14. Which responsibilities look like domain-level assignments?
```sql
WITH n AS (
    SELECT snapshot_date, domain_id, count(*) AS assets
    FROM dim_asset GROUP BY 1, 2
),
c AS (
    SELECT a.snapshot_date, a.domain_id, r.role_name, r.user_id,
           count(DISTINCT r.asset_id) AS covered
    FROM fact_responsibility r
    JOIN dim_asset a ON a.snapshot_date = r.snapshot_date AND a.asset_id = r.asset_id
    WHERE r.user_id IS NOT NULL AND r.asset_resolution = 'in_export'
    GROUP BY 1, 2, 3, 4
)
SELECT d.domain_name, c.role_name, c.user_id, c.covered, n.assets,
       round(100.0 * c.covered / n.assets, 1) AS pct_of_domain
FROM c
JOIN n ON n.snapshot_date = c.snapshot_date AND n.domain_id = c.domain_id
JOIN dim_domain d ON d.snapshot_date = c.snapshot_date AND d.domain_id = c.domain_id
WHERE n.assets >= 5 AND c.covered = n.assets
ORDER BY n.assets DESC
LIMIT 25
```
*Reads as:* a person-role pair that covers **every** asset of a domain with at least 5 assets is almost certainly assigned on the domain and expanded onto its assets by the export, not set asset by asset. Useful to separate real stewardship from inheritance before counting workload (*Who is responsible for how much?*).
*Watch out:* a heuristic, not a fact: the export has no direct/inherited flag.

---

## Relationships and lineage-style questions

### 15. Which assets have no relations at all?
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

### 16. Which assets are the most connected?
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

### 17. What is connected to this asset? (impact analysis, up to 3 hops)
```sql
WITH RECURSIVE start AS (
    SELECT snapshot_date, asset_id FROM dim_asset
    WHERE asset_display_name = 'My Business Term'
),
reach(snapshot_date, asset_id, hops) AS (
    SELECT snapshot_date, asset_id, 0 FROM start
    UNION
    SELECT r.snapshot_date,
           CASE WHEN r.asset_id1 = x.asset_id THEN r.asset_id2 ELSE r.asset_id1 END,
           x.hops + 1
    FROM reach x
    JOIN fact_relation r
      ON r.snapshot_date = x.snapshot_date
     AND (r.asset_id1 = x.asset_id OR r.asset_id2 = x.asset_id)
    WHERE x.hops < 3
)
SELECT min(x.hops) AS hops, a.asset_type_name, a.asset_display_name, a.domain_name
FROM reach x
JOIN dim_asset a ON a.snapshot_date = x.snapshot_date AND a.asset_id = x.asset_id
WHERE x.hops > 0
GROUP BY a.asset_id, a.asset_type_name, a.asset_display_name, a.domain_name
ORDER BY 1, 2, 3
```
*Reads as:* everything within three relation hops of the asset, nearest first. Replace `'My Business Term'` (add a domain filter if names repeat).
*Watch out:* relations are followed in **both** directions and **all relation types are mixed** (the export has no type names), so the result grows fast. This approximates *business* impact; it is **not technical lineage**, which is not part of Insights.

### 18. How do asset types connect to each other?
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

### 19. How did inventory change over time?
```sql
SELECT snapshot_date, asset_type_name, count(*) AS assets
FROM dim_asset
GROUP BY 1, 2
ORDER BY 1, 3 DESC
```

### 20. What was added between two snapshots?
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

### 21. When was content created?
```sql
SELECT date_trunc('month', CAST(creation_date AS TIMESTAMP)) AS month, asset_type_name, count(*) AS created
FROM dim_asset
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
```
*Watch out:* a bulk import shows up as one huge month.

---

## Tags and attributes

### 22. Is definition coverage improving?
```sql
WITH defined AS (
    SELECT DISTINCT snapshot_date, asset_id
    FROM fact_attribute
    WHERE attribute_type_name = 'Definition' AND coalesce(value_as_text, '') <> ''
)
SELECT a.snapshot_date, count(*) AS terms, count(d.asset_id) AS with_definition,
       round(100.0 * count(d.asset_id) / count(*), 1) AS pct_defined
FROM dim_asset a
LEFT JOIN defined d ON d.snapshot_date = a.snapshot_date AND d.asset_id = a.asset_id
WHERE a.asset_type_name = 'Business Term'
GROUP BY 1
ORDER BY 1
```
*Reads as:* the governance KPI over time. Needs several snapshots; month-end snapshots are enough and outlive the 31-day window.

### 23. Which tags are used most?
```sql
SELECT tag_name, count(DISTINCT asset_id) AS assets
FROM bridge_asset_tag
GROUP BY 1
ORDER BY 2 DESC
```

### 24. Which sensitive-tagged assets have no owner?
```sql
SELECT a.asset_type_name, a.domain_name, count(*) AS tagged_without_owner
FROM bridge_asset_tag t
JOIN dim_asset a ON a.snapshot_date = t.snapshot_date AND a.asset_id = t.asset_id
WHERE t.tag_name = 'PII'
  AND NOT EXISTS (
      SELECT 1 FROM fact_responsibility r
      WHERE r.snapshot_date = a.snapshot_date
        AND r.asset_id = a.asset_id
        AND r.role_name = 'Owner')
GROUP BY 1, 2
ORDER BY 3 DESC
```
*Reads as:* a risk list: sensitive content nobody is accountable for. Replace `'PII'` with the client's tag (`SELECT tag_name, count(*) FROM bridge_asset_tag GROUP BY 1` lists them).
*Watch out:* same ownership caveat as *Which Business Terms have no owner?* (community-level owners are invisible).

### 25. Which attribute types are used most, and how are they typed?
```sql
SELECT attribute_type_name, kind, count(*) AS values_, count(DISTINCT asset_id) AS assets
FROM fact_attribute
GROUP BY 1, 2
ORDER BY 3 DESC
```

---

## Usage Analytics (needs the optional `view_events` table)

These recipes only run if your snapshots contain `view_events` (check with `collibra-insights tables-available`). Only **user-interface** events are counted, usernames are personal data, and `snapshot_date` in this table is the day the event happened. The columns come from Collibra's documentation; they were not available on the reference instance to verify.

### 26. How many people use Collibra each day?
```sql
SELECT snapshot_date AS day, count(DISTINCT user_id) AS active_users, count(*) AS views
FROM fact_view_event
GROUP BY 1
ORDER BY 1
```

### 27. Which assets are viewed most?
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

### 28. Which content is never viewed?
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

# Client playbook: applying Insights at a new client

A repeatable checklist. Allow about an hour for the first run. Nothing here assumes anything about the client's instance beyond the licence.

## 0. Before you start

| Need | Detail |
|---|---|
| Licence and version | Collibra Insights licence, Platform 5.7+ |
| Access | **Preferred:** an *integration* OAuth application registered by the client's administrator (Settings → OAuth Applications), with permission to download reporting data (confirmed sufficient for `ping` and `download` on the reference instance). Otherwise a dedicated technical user. Avoid personal accounts |
| Where to run | Your machine or a client-approved host. Snapshots contain governance data and personal data: keep them off shared drives and out of git (`snapshots/` is git-ignored) |
| Install | `pip install -e ".[dev]"` from this repository |

Set credentials without leaving them in your shell history. **OAuth (preferred):**
```bash
export COLLIBRA_URL=https://<client>.collibra.com
export COLLIBRA_CLIENT_ID=<application client id>
read -s COLLIBRA_CLIENT_SECRET   # run on its own line; type or paste, then Enter (nothing is echoed)
export COLLIBRA_CLIENT_SECRET
```
or basic authentication with a technical user (`COLLIBRA_USER`, and `read -s COLLIBRA_PASSWORD` then `export COLLIBRA_PASSWORD`). **Run each `read -s` as its own command**: if more lines follow when you paste, they get swallowed as the secret. See [the client docs](../client.md#authentication) for details.

## 1. Check connectivity (1 min)

```bash
collibra-toolkit ping
```
Five lines, no content; the last says which authentication method was really used, so check it matches what you intended (an empty secret silently falls back to basic). A 401 is credentials; a 403 is a missing permission or licence.

## 2. See what the client's ZIP contains (2 min)

```bash
collibra-insights tables-available <yesterday> <a month-end> --endpoint both
```
Compare against the eight core tables. Note whether `view_events` is present and whether the two endpoints differ. If `view_events` is absent on both endpoints and both dates, it is not provisioned for this client: ask their administrator or Collibra support (wording in [known-gaps.md](known-gaps.md) 2d).

## 3. Download and explore (5 min)

```bash
collibra-insights download <yesterday>
collibra-insights explore  snapshots/insights-<yesterday>
```
`explore` prints every table with row counts and columns. Compare with [data-dictionary.md](data-dictionary.md); report any difference (a different Collibra version may add or rename columns).

## 4. Measure the data quality of the export (10 min)

```bash
collibra-insights check        snapshots/insights-<yesterday>
collibra-insights investigate  snapshots/insights-<yesterday> --live | tee investigate-live.txt
```
Interpret with [known-gaps.md](known-gaps.md). Record, for this client: hidden-by-default and omitted meta object counts, which roles have responsibilities that match no asset (and why), and whether `view_events` exists.

## 5. Get history (optional)

Download several dates into `snapshots/` and point tools at the parent folder (`snapshots/`): tables from all snapshots are unioned and `snapshot_date` tells them apart. Retention is 31 daily snapshots, then month-ends, then year-ends, so start collecting early.

## 6. Answer the client's questions

Open the [cookbook](cookbook.md). Replace type, role and attribute names with the client's (`SELECT DISTINCT attribute_type_name FROM fact_attribute` and `SELECT DISTINCT role_name FROM fact_responsibility` list them). Always read the "Watch out" note before presenting a number.

## 7. Hand over

Give the client: the export-vs-UI reconciliation from step 4, the list of known gaps that affect their questions, and the exact commands, so they can rerun them.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| 401 on any call | wrong user/password or client id/secret (check the entry; see the `read -s` note). With OAuth the message may say the token request was rejected: the secret or application registration is wrong |
| 403 on download | the user lacks permission, or no Insights licence |
| 404 on download | snapshot not generated yet (try the day before), or outside retention |
| `ModuleNotFoundError` after `git pull` | the editable install broke; run `pip install -e .` again. On macOS keep the virtualenv outside iCloud-synced folders such as Desktop |
| `429` or `5xx` errors | the client already retries with backoff (up to 4 times, honouring `Retry-After`); a persistent `CollibraRateLimitError`/`CollibraServerError` means back off for longer or ask the client about rate limits |
| Retention warning | the date is outside the documented tiers; the request may still work |

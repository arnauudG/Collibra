# collibra-insights

A small Python package to **download Collibra Insights Data Access snapshots** and **explore them locally** with DuckDB. Companion guides explain what the data is and how to model it:

- [`docs/insights-data-access.md`](docs/insights-data-access.md): what Insights Data Access is, how it is delivered, retention, and the tables
- [`docs/data-modeling.md`](docs/data-modeling.md): how to model the tables (dimensions, facts, snapshots, pivoting attributes)

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

export COLLIBRA_URL=https://<your-env>.collibra.com
export COLLIBRA_USER=...  COLLIBRA_PASSWORD=...     # or COLLIBRA_TOKEN=...

collibra-insights download 2026-10-10                # -> snapshots/insights-2026-10-10/
collibra-insights explore snapshots/insights-2026-10-10
collibra-insights query snapshots/insights-2026-10-10 "select count(*) from asset"
collibra-insights check snapshots/insights-2026-10-10   # build the model + conformance report
```

```python
from collibra_insights import Snapshot
s = Snapshot("snapshots/insights-2026-10-10")
print(s.report())                       # every table, row count, columns + types
s.sql("select count(*) from asset").fetchall()
```

## Status (honest)

| Piece | State |
|---|---|
| Date validation, download, safe unzip, DuckDB views, schema discovery | Implemented, unit-tested against **fake** HTTP and **synthetic** Parquet |
| Run against a real Collibra environment | **Done once** (training instance, snapshot 2026-10-10): download + explore of all 8 tables worked |
| Column-level schema | Observed and documented in `docs/data-modeling.md`; still **discovered at runtime**, not hardcoded |
| Table grain / hierarchy / relation direction | Inferred from column names; verify with the `query` command (see `docs/data-modeling.md` §5) |
| Star-schema views + `check` | Implemented (`model.py`), tested on **synthetic** data with real column names; not yet run on the real snapshot |

Requires Collibra Platform 5.7+ and a Collibra Insights licence. Snapshots may contain sensitive governance data and are git-ignored.

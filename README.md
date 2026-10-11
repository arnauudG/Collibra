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
| Run against a real Collibra environment | **Not yet done**; needs credentials + an Insights licence |
| Column-level schema | **Not hardcoded on purpose**: Collibra's public docs name the tables but not the columns. Run `explore` on a real snapshot, then fill in `docs/data-modeling.md`. |

Requires Collibra Platform 5.7+ and a Collibra Insights licence. Snapshots may contain sensitive governance data and are git-ignored.

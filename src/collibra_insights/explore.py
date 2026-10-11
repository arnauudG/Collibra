"""Explore an extracted Insights snapshot locally with DuckDB."""

from __future__ import annotations

from pathlib import Path

import duckdb

from .tables import DOCUMENTED_TABLES


class Snapshot:
    """Each folder of Parquet files in the snapshot becomes a DuckDB view named after the folder."""

    def __init__(self, path: str | Path, database: str = ":memory:"):
        self.path = Path(path)
        self.con = duckdb.connect(database)
        self.tables: list[str] = []
        for folder in sorted({p.parent for p in self.path.rglob("*.parquet")}):
            name = folder.name
            glob = (folder / "*.parquet").as_posix().replace("'", "''")
            self.con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM read_parquet(\'{glob}\')')
            self.tables.append(name)
        if not self.tables:
            raise FileNotFoundError(f"no .parquet files under {self.path}")

    def undocumented(self) -> list[str]:
        """Tables present in the snapshot that Collibra's docs do not name (e.g. usage analytics)."""
        return [t for t in self.tables if t not in DOCUMENTED_TABLES]

    def missing(self) -> list[str]:
        return [t for t in DOCUMENTED_TABLES if t not in self.tables]

    def describe(self, table: str):
        """Column names and types, straight from the Parquet files."""
        return self.con.execute(f'DESCRIBE "{table}"').fetchall()

    def row_counts(self) -> dict[str, int]:
        return {t: self.con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in self.tables}

    def sql(self, query: str):
        return self.con.execute(query)

    def report(self) -> str:
        lines = []
        counts = self.row_counts()
        for t in self.tables:
            note = DOCUMENTED_TABLES.get(t, "(not named in Collibra docs)")
            lines.append(f"{t}  [{counts[t]} rows]  {note}")
            for col, typ, *_ in self.describe(t):
                lines.append(f"    {col}: {typ}")
        return "\n".join(lines)

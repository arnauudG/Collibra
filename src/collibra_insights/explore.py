"""Explore an extracted Insights snapshot locally with DuckDB."""

from __future__ import annotations

from pathlib import Path

import duckdb

from .tables import DOCUMENTED_TABLES


class Snapshot:
    """Each table folder of Parquet files becomes a DuckDB view named after it.

    ``path`` may be one snapshot folder or a parent holding several (``snapshots/``): the same
    table from every snapshot is unioned, and ``snapshot_date`` tells them apart (history/trends).
    """

    def __init__(self, path: str | Path, database: str = ":memory:"):
        self.path = Path(path)
        self.con = duckdb.connect(database)
        self.tables: list[str] = []
        groups: dict[str, list[Path]] = {}
        for folder in sorted(self._table_folders()):
            groups.setdefault(folder.name, []).append(folder)  # same table in several snapshots -> one view
        for name, folders in sorted(groups.items()):
            globs = ", ".join("'" + (f / "**" / "*.parquet").as_posix().replace("'", "''") + "'" for f in folders)
            self.con.execute(
                f'CREATE OR REPLACE VIEW "{name}" AS '
                f"SELECT * FROM read_parquet([{globs}], hive_partitioning=true, union_by_name=true)"
            )
            self.tables.append(name)
        if not self.tables:
            raise FileNotFoundError(f"no .parquet files under {self.path}")

    def _table_folders(self) -> set[Path]:
        """Real snapshots are Hive-partitioned: <table>/snapshot_date_year=.../.../file.parquet.

        A table is the folder just above the first ``key=value`` partition folder,
        or the file's own folder when the layout is flat.
        """
        folders = set()
        for f in self.path.rglob("*.parquet"):
            rel = f.relative_to(self.path).parent
            parts = rel.parts
            depth = next((i for i, p in enumerate(parts) if "=" in p), len(parts))
            folders.add(self.path.joinpath(*parts[:depth]) if depth else self.path)
        return folders

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

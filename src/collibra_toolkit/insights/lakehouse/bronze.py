"""Bronze: land the raw snapshot files unchanged, with a manifest proving what arrived.

Raw files are never rewritten, so bronze is the system of record and the way to keep history beyond
Collibra's 31-day window. Needs the store only to count rows.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ..store import Snapshot
from ..tables import table_depth


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_separate(source: str | Path, output: str | Path) -> None:
    """Output inside the source (or the reverse) would be read back as data on the next run."""
    s, o = Path(source).resolve(), Path(output).resolve()
    if o == s or o.is_relative_to(s) or s.is_relative_to(o):
        raise ValueError(f"output folder {output} must be separate from the snapshot folder {source}")


def land(snapshot_dir: str | Path, bronze_dir: str | Path) -> dict:
    """Copy ``<table>/<partitions>/*.parquet`` under ``bronze_dir`` keeping the relative layout.

    Idempotent: a file already there with the same hash is skipped; one with a different hash is
    replaced and reported. Writes ``_manifests/<utc>-<source>.json`` and returns the manifest.
    """
    ensure_separate(snapshot_dir, bronze_dir)
    src, dest = Path(snapshot_dir), Path(bronze_dir)
    files, replaced = [], []
    for f in sorted(src.rglob("*.parquet")):
        parts = f.relative_to(src).parent.parts
        depth = table_depth(parts)
        rel = Path(*parts[depth - 1:], f.name) if depth else Path(src.name, f.name)  # drop any wrapper folder
        target = dest / rel
        digest = _sha256(f)
        if target.exists():
            if _sha256(target) != digest:
                replaced.append(rel.as_posix())
                shutil.copy2(f, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
        files.append({"path": rel.as_posix(), "bytes": f.stat().st_size, "sha256": digest})
    manifest = {
        "landed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": src.name,
        "rows_in_source": Snapshot(src).row_counts(),
        "files": files,
        "replaced": replaced,
    }
    mdir = dest / "_manifests"
    mdir.mkdir(parents=True, exist_ok=True)
    stamp = manifest["landed_at"].replace(":", "").replace("+0000", "Z").replace("+00:00", "Z")
    (mdir / f"{stamp}-{src.name}.json").write_text(json.dumps(manifest, indent=2))
    return manifest

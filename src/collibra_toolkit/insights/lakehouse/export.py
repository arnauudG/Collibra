"""Write the medallion layers: bronze (raw), silver (model), gold (reporting tables)."""

from __future__ import annotations

import json
from pathlib import Path

from ..model import GoldConfig, build_gold, build_model
from ..store import Snapshot
from .bronze import ensure_separate, land

LAYERS = ("bronze", "silver", "gold")
NAMESPACE = "insights"  # <out>/<layer>/insights/<table>: room for other initiatives in the same lake


def load_gold_config(path: str | Path | None) -> GoldConfig:
    """Read a JSON file whose keys are ``GoldConfig`` fields (lists become tuples)."""
    if not path:
        return GoldConfig()
    data = json.loads(Path(path).read_text())
    unknown = set(data) - set(GoldConfig.__dataclass_fields__)
    if unknown:
        raise ValueError(f"unknown gold config keys: {sorted(unknown)}")
    return GoldConfig(**{k: tuple(v) if isinstance(v, list) else v for k, v in data.items()})


def export_layers(snapshot_path: str | Path, out_dir: str | Path, layers=LAYERS, gold: GoldConfig | None = None) -> dict:
    """Export the requested layers under ``<out_dir>/<layer>/insights/``. Returns what was written."""
    ensure_separate(snapshot_path, out_dir)
    out, report = Path(out_dir), {}
    snap = Snapshot(snapshot_path)
    if "bronze" in layers:
        manifest = land(snapshot_path, out / "bronze" / NAMESPACE)
        report["bronze"] = {"files": len(manifest["files"]), "replaced": len(manifest["replaced"]), "rows": manifest["rows_in_source"]}
    if "silver" in layers or "gold" in layers:
        silver = build_model(snap)
        if "silver" in layers:
            report["silver"] = snap.export(silver, out / "silver" / NAMESPACE)
        if "gold" in layers:
            report["gold"] = snap.export(build_gold(snap, gold), out / "gold" / NAMESPACE)
    return report

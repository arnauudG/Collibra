"""The three layers end to end."""

import json

import duckdb
import pytest

from collibra_toolkit.insights.lakehouse import export_layers, land, load_gold_config
from collibra_toolkit.insights.model import GoldConfig


def test_all_layers_land_under_their_own_folder(snap, lake):
    report = export_layers(snap.path, lake, gold=GoldConfig(governed_types=("Term",)))
    assert set(report) == {"bronze", "silver", "gold"}
    assert (lake / "bronze" / "insights" / "asset").is_dir()
    assert (lake / "silver" / "insights" / "dim_asset").is_dir()
    assert (lake / "gold" / "insights" / "gold_governance_scorecard").is_dir()
    assert report["silver"]["dim_asset"] == 2 and report["gold"]["gold_governance_scorecard"] == 2


def test_silver_keeps_personal_data_out_by_default(snap, lake):
    export_layers(snap.path, lake, layers=("silver",))
    cols = duckdb.sql(f"SELECT * FROM read_parquet('{lake}/silver/insights/dim_user/**/*.parquet', hive_partitioning=true)").columns
    assert "username" in cols and "user_email" not in cols and "user_firstname" not in cols


def test_a_single_layer_can_be_requested(snap, lake):
    export_layers(snap.path, lake, layers=("gold",))
    assert not (lake / "bronze").exists() and not (lake / "silver").exists()
    assert (lake / "gold").is_dir()


def test_gold_config_file(tmp_path):
    f = tmp_path / "gold.json"
    f.write_text(json.dumps({"governed_types": ["Business Term", "Data Set"], "owner_roles": ["Data Owner"], "stale_days": 180}))
    cfg = load_gold_config(f)
    assert cfg.governed_types == ("Business Term", "Data Set") and cfg.owner_roles == ("Data Owner",) and cfg.stale_days == 180
    assert load_gold_config(None) == GoldConfig()
    f.write_text(json.dumps({"governed_type": ["typo"]}))
    with pytest.raises(ValueError, match="unknown gold config keys"):
        load_gold_config(f)


def test_output_inside_the_snapshot_folder_is_refused(snap):
    with pytest.raises(ValueError, match="must be separate"):
        export_layers(snap.path, snap.path / "lake")
    with pytest.raises(ValueError, match="must be separate"):
        land(snap.path, snap.path / "bronze")

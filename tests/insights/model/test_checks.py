"""Conformance checks over the model."""

import datetime as dt
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from collibra_toolkit.insights.store import Snapshot
from collibra_toolkit.insights.model import build_model, check_model


def test_checks_report_orphan_only(snap):
    res = check_model(snap)
    assert res["asset_missing_domain"] == 1
    assert res["relation_missing_asset"] == 0 and res["community_parent_mismatch"] == 0
    assert res["relation_ids_not_stored_twice"] == 0
    assert res["dim_asset_duplicate_keys"] == 0 and res["dim_community_duplicate_keys"] == 0

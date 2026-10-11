"""Shared Insights fixtures: a synthetic snapshot with the REAL column names of an export."""

import pytest

from collibra_toolkit.insights.store import Snapshot
from tests.insights.helpers import write_fixture_snapshot


@pytest.fixture
def snap(tmp_path):
    write_fixture_snapshot(tmp_path)
    return Snapshot(tmp_path)

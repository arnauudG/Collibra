"""Snapshot-date validation and the documented retention tiers."""

import datetime as dt
import pytest
from tests.support.fakes import FakeResp, FakeSession, zip_bytes
from collibra_toolkit import CollibraClient, CollibraError, CollibraNotFound
from collibra_toolkit.insights.api import InsightsClient
from collibra_toolkit.insights.api import retention_note, validate_snapshot_date


TODAY = dt.date(2026, 10, 11)


def test_date_validation():
    assert validate_snapshot_date("2026-10-01", TODAY) == dt.date(2026, 10, 1)
    for bad in ("2026-10-12", "10/01/2026"):
        with pytest.raises(CollibraError):
            validate_snapshot_date(bad, TODAY)


def test_retention_is_a_warning_not_an_error():
    assert retention_note(dt.date(2026, 10, 1), TODAY) is None  # last 31 days
    assert retention_note(dt.date(2026, 6, 30), TODAY) is None  # month-end within 12 months
    assert retention_note(dt.date(2024, 12, 31), TODAY) is None  # year-end, any age
    assert retention_note(dt.date(2026, 6, 29), TODAY)  # ordinary old day
    assert retention_note(dt.date(2024, 6, 30), TODAY)  # month-end older than 12 months
    with pytest.warns(UserWarning):
        validate_snapshot_date("2026-06-29", TODAY)

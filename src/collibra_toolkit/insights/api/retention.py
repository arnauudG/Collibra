"""Snapshot-date rules from Collibra's documented retention. No network, no client."""

from __future__ import annotations

import calendar
import datetime as dt
import warnings

from ...client import CollibraError


def retention_note(d: dt.date, today: dt.date) -> str | None:
    """Collibra's documented retention: every day for 31 days, month-ends for 12 months,
    year-ends indefinitely. Return a message if ``d`` falls outside that, else None."""
    age = (today - d).days
    month_end = d.day == calendar.monthrange(d.year, d.month)[1]
    year_end = d.month == 12 and d.day == 31
    if age <= 31 or (month_end and age <= 366) or year_end:
        return None
    return (
        f"{d} is outside the documented retention (last 31 days, month-ends for 12 months, "
        "year-ends after that); the request may fail"
    )


def validate_snapshot_date(value: str | dt.date, today: dt.date | None = None) -> dt.date:
    """Reject malformed or future dates. Retention gaps only *warn*: Collibra's own pages
    word the rule differently, so we don't block a request the server might still honour."""
    today = today or dt.date.today()
    try:
        d = value if isinstance(value, dt.date) else dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise CollibraError(f"snapshot date must be YYYY-MM-DD, got {value!r}") from None
    if d > today:
        raise CollibraError(f"snapshot date {d} is in the future")
    note = retention_note(d, today)
    if note:
        warnings.warn(note, stacklevel=2)
    return d

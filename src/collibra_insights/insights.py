"""Insights Data Access on top of a generic ``CollibraClient``."""

from __future__ import annotations

import calendar
import datetime as dt
import os
import shutil
import warnings
import zipfile
from pathlib import Path

from .client import CollibraClient, CollibraError, CollibraNotFound

DIRECT_DOWNLOAD = "/reporting/insights/directDownload"  # relative to /rest/2.0


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


class InsightsClient:
    def __init__(self, client: CollibraClient):
        self.client = client

    @classmethod
    def from_env(cls, **kwargs) -> InsightsClient:
        return cls(CollibraClient.from_env(**kwargs))

    def download_snapshot(self, snapshot_date: str | dt.date, dest: str | Path) -> Path:
        """Download and extract one Insights snapshot; return the extraction folder.

        directDownload answers with a redirect to a pre-signed cloud-storage URL
        (valid ~60s), so redirects must be followed. ``requests`` drops the
        Authorization header on cross-host redirects, which is what we want.
        """
        d = validate_snapshot_date(snapshot_date)
        dest = Path(dest)
        out = dest / f"insights-{d.isoformat()}"
        dest.mkdir(parents=True, exist_ok=True)
        zip_path = dest / f"insights-{d.isoformat()}.zip"
        part = zip_path.with_name(zip_path.name + ".part")
        staging = dest / f".insights-{d.isoformat()}.extracting"

        try:
            try:
                resp = self.client.request(
                    "GET", DIRECT_DOWNLOAD, params={"snapshotDate": d.isoformat(), "format": "zip"}, stream=True
                )
            except CollibraNotFound as exc:
                raise CollibraNotFound(
                    404, f"no snapshot for {d}: not generated yet, or outside retention"
                ) from exc
            try:
                with open(part, "wb") as fh:  # never leave a half-written .zip behind
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            finally:
                resp.close()
            os.replace(part, zip_path)

            shutil.rmtree(staging, ignore_errors=True)
            try:
                with zipfile.ZipFile(zip_path) as zf:
                    for name in zf.namelist():  # guard against zip-slip
                        if not (staging / name).resolve().is_relative_to(staging.resolve()):
                            raise CollibraError(f"unsafe path in archive: {name}")
                    zf.extractall(staging)
            except zipfile.BadZipFile:
                zip_path.unlink(missing_ok=True)
                raise CollibraError("downloaded file is not a valid ZIP") from None
            shutil.rmtree(out, ignore_errors=True)  # no stale files from an earlier extraction
            staging.rename(out)
        finally:
            part.unlink(missing_ok=True)
            shutil.rmtree(staging, ignore_errors=True)
        return out

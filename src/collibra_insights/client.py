"""Minimal Collibra REST client, scoped to downloading Insights snapshots."""

from __future__ import annotations

import calendar
import datetime as dt
import zipfile
from pathlib import Path

import requests

DIRECT_DOWNLOAD = "/rest/2.0/reporting/insights/directDownload"


class CollibraError(Exception):
    pass


def validate_snapshot_date(value: str | dt.date, today: dt.date | None = None) -> dt.date:
    """Collibra keeps the last 31 daily snapshots plus each month-end (see docs).

    Raise early with a clear message rather than waiting for an opaque HTTP error.
    """
    today = today or dt.date.today()
    try:
        d = value if isinstance(value, dt.date) else dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise CollibraError(f"snapshot date must be YYYY-MM-DD, got {value!r}") from None
    month_end = d.day == calendar.monthrange(d.year, d.month)[1]
    if d > today:
        raise CollibraError(f"snapshot date {d} is in the future")
    if (today - d).days > 31 and not month_end:
        raise CollibraError(
            f"{d} is older than 31 days and not a month-end; only those snapshots are retained"
        )
    return d


class CollibraClient:
    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        token: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            self.session.auth = (username, password)
        else:
            raise CollibraError("provide username+password or token")

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

        resp = self.session.get(
            self.base_url + DIRECT_DOWNLOAD,
            params={"snapshotDate": d.isoformat(), "format": "zip"},
            stream=True,
            allow_redirects=True,
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise CollibraError(f"download failed: HTTP {resp.status_code} {resp.text[:200]!r}")
        with open(zip_path, "wb") as fh:
            for chunk in resp.iter_content(1 << 20):
                fh.write(chunk)
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():  # guard against zip-slip
                if not (out / name).resolve().is_relative_to(out.resolve()):
                    raise CollibraError(f"unsafe path in archive: {name}")
            zf.extractall(out)
        return out

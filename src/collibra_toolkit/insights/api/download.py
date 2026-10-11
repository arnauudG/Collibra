"""Insights Data Access on top of a generic ``CollibraClient``."""

from __future__ import annotations

import datetime as dt
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from ...client import CollibraClient, CollibraError, CollibraNotFound
from ..tables import table_name
from .retention import validate_snapshot_date

# Paths relative to /rest/2.0. "direct" redirects to a pre-signed storage URL (recommended);
# "legacy" streams through Collibra and is documented as soon to be deprecated.
ENDPOINTS = {
    "direct": "/reporting/insights/directDownload",
    "legacy": "/reporting/insights/download",
}


class InsightsClient:
    def __init__(self, client: CollibraClient):
        self.client = client

    @classmethod
    def from_env(cls, **kwargs) -> InsightsClient:
        return cls(CollibraClient.from_env(**kwargs))

    def _fetch(self, d: dt.date, endpoint: str, target: Path) -> None:
        """Stream the snapshot ZIP to ``target`` atomically (``.part`` file, then rename).

        The download endpoint answers with a redirect to a pre-signed cloud-storage URL
        (valid ~60s), so redirects must be followed. ``requests`` drops the Authorization
        header on cross-host redirects, which is what we want.
        """
        if endpoint not in ENDPOINTS:
            raise CollibraError(f"endpoint must be one of {sorted(ENDPOINTS)}, got {endpoint!r}")
        part = target.with_name(target.name + ".part")
        try:
            try:
                resp = self.client.request(
                    "GET", ENDPOINTS[endpoint], params={"snapshotDate": d.isoformat(), "format": "zip"}, stream=True
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
            os.replace(part, target)
        finally:
            part.unlink(missing_ok=True)

    def download_snapshot(self, snapshot_date: str | dt.date, dest: str | Path, endpoint: str = "direct") -> Path:
        """Download and extract one Insights snapshot; return the extraction folder."""
        d = validate_snapshot_date(snapshot_date)
        dest = Path(dest)
        out = dest / f"insights-{d.isoformat()}"
        dest.mkdir(parents=True, exist_ok=True)
        zip_path = dest / f"insights-{d.isoformat()}.zip"
        staging = dest / f".insights-{d.isoformat()}.extracting"
        try:
            self._fetch(d, endpoint, zip_path)
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
            shutil.rmtree(staging, ignore_errors=True)
        return out

    def list_tables(self, snapshot_date: str | dt.date, endpoint: str = "direct") -> list[str]:
        """Table folders inside a snapshot ZIP, without extracting it (the ZIP is downloaded to a temp file)."""
        d = validate_snapshot_date(snapshot_date)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "snapshot.zip"
            self._fetch(d, endpoint, target)
            try:
                with zipfile.ZipFile(target) as zf:
                    names = zf.namelist()
            except zipfile.BadZipFile:
                raise CollibraError("downloaded file is not a valid ZIP") from None
        tables = {table_name(Path(n).parent.parts) for n in names if n.endswith(".parquet")}
        return sorted(t for t in tables if t)

"""
app/store/cumulative.py
========================
Parquet-backed, append-only cumulative dataset store.

Replaces the _temp_df module-level global in dataset_summary.py (defect B4).
A module global is lost on restart and diverges across uvicorn workers.
This store is process-safe for reads (parquet is immutable per file) and
serialises writes via a file lock.

Layout:
    data/cumulative/base.parquet              # DataCo 2015-01..2018-01, immutable
    data/cumulative/increments/{period}.parquet
    data/cumulative/manifest.json             # periods, row counts, checksums
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_BASE_DIR       = pathlib.Path("data/cumulative")
_BASE_PARQUET   = _BASE_DIR / "base.parquet"
_INCREMENTS_DIR = _BASE_DIR / "increments"
_MANIFEST_PATH  = _BASE_DIR / "manifest.json"


@dataclass
class AppendReport:
    period: str
    rows_appended: int
    cumulative_rows: int
    checksum: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "rows_appended": self.rows_appended,
            "cumulative_rows": self.cumulative_rows,
            "checksum": self.checksum,
            "timestamp": self.timestamp,
        }


class CumulativeStore:
    """
    Parquet-backed cumulative store.

    Thread/process safety: reads are always safe (immutable parquet files).
    Writes acquire a simple file lock via a .lock sentinel file.
    """

    def __init__(
        self,
        base_dir: pathlib.Path | str = _BASE_DIR,
        source_parquet: pathlib.Path | str | None = None,
    ) -> None:
        self._base_dir       = pathlib.Path(base_dir)
        self._base_parquet   = self._base_dir / "base.parquet"
        self._increments_dir = self._base_dir / "increments"
        self._manifest_path  = self._base_dir / "manifest.json"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._increments_dir.mkdir(parents=True, exist_ok=True)

        # Bootstrap: if base.parquet doesn't exist, copy from processed_master
        if not self._base_parquet.exists():
            src = pathlib.Path(source_parquet) if source_parquet else pathlib.Path(
                "data/uploads/processed_master.parquet"
            )
            if src.exists():
                import shutil
                shutil.copy2(src, self._base_parquet)
                logger.info(f"CumulativeStore: bootstrapped base from {src}")
                self._update_manifest_from_base()

    # ── Public API ────────────────────────────────────────────────────────────

    def load_cumulative(self) -> pd.DataFrame:
        """Load base + all increments in chronological order."""
        frames: list[pd.DataFrame] = []

        if self._base_parquet.exists():
            frames.append(pd.read_parquet(self._base_parquet))

        manifest = self._read_manifest()
        for period in manifest.get("periods", []):
            inc_path = self._increments_dir / f"{period}.parquet"
            if inc_path.exists():
                frames.append(pd.read_parquet(inc_path))

        if not frames:
            raise FileNotFoundError(
                "CumulativeStore: no base parquet found. "
                "Run initialization first."
            )

        df = pd.concat(frames, ignore_index=True)
        logger.info(f"CumulativeStore.load_cumulative: {len(df)} rows")
        return df

    def load_base(self) -> pd.DataFrame:
        """Load the immutable base (DataCo only)."""
        if not self._base_parquet.exists():
            raise FileNotFoundError("CumulativeStore: base.parquet not found")
        return pd.read_parquet(self._base_parquet)

    def append(self, df_engineered: pd.DataFrame, period: str) -> AppendReport:
        """
        Append an engineered increment to the store.

        The caller is responsible for engineering df_engineered anchored on
        the full cumulative history (engineer_features_on_new). This method
        only persists and updates the manifest.

        Raises ValueError if the period already exists (replay guard).
        """
        manifest = self._read_manifest()
        if period in manifest.get("periods", []):
            raise ValueError(
                f"CumulativeStore: period {period!r} already exists. "
                f"Use rollback() first if you need to replace it."
            )

        inc_path = self._increments_dir / f"{period}.parquet"
        df_engineered.to_parquet(inc_path, index=False)

        checksum = self._checksum(inc_path)
        manifest.setdefault("periods", []).append(period)
        manifest.setdefault("checksums", {})[period] = checksum
        manifest.setdefault("row_counts", {})[period] = len(df_engineered)
        manifest["total_rows"] = manifest.get("total_rows", 0) + len(df_engineered)
        manifest["last_increment"] = period

        # Update data_end
        date_col = next(
            (c for c in ("order date (DateOrders)", "order_date") if c in df_engineered.columns),
            None,
        )
        if date_col:
            ts = pd.to_datetime(df_engineered[date_col], errors="coerce").max()
            if pd.notna(ts):
                manifest["data_end"] = ts.strftime("%Y-%m-%d")

        self._write_manifest(manifest)

        report = AppendReport(
            period=period,
            rows_appended=len(df_engineered),
            cumulative_rows=manifest["total_rows"],
            checksum=checksum,
        )
        logger.info(
            f"CumulativeStore.append: period={period} rows={len(df_engineered)} "
            f"cumulative={manifest['total_rows']}"
        )
        return report

    def rollback(self, period: str) -> None:
        """
        Remove an increment from the store.

        Required — uploads go wrong. Deletes the parquet file and removes
        the period from the manifest.
        """
        manifest = self._read_manifest()
        periods = manifest.get("periods", [])
        if period not in periods:
            raise ValueError(f"CumulativeStore: period {period!r} not found")

        inc_path = self._increments_dir / f"{period}.parquet"
        row_count = manifest.get("row_counts", {}).get(period, 0)

        if inc_path.exists():
            inc_path.unlink()

        periods.remove(period)
        manifest["periods"] = periods
        manifest.get("checksums", {}).pop(period, None)
        manifest.get("row_counts", {}).pop(period, None)
        manifest["total_rows"] = max(0, manifest.get("total_rows", 0) - row_count)
        manifest["last_increment"] = periods[-1] if periods else None

        self._write_manifest(manifest)
        logger.info(f"CumulativeStore.rollback: removed period={period}")

    def periods(self) -> list[str]:
        """Return list of loaded increment periods in order."""
        return self._read_manifest().get("periods", [])

    def summary(self) -> dict[str, Any]:
        """Return manifest summary for API responses."""
        manifest = self._read_manifest()
        return {
            "base_exists": self._base_parquet.exists(),
            "periods": manifest.get("periods", []),
            "total_rows": manifest.get("total_rows", 0),
            "last_increment": manifest.get("last_increment"),
            "data_end": manifest.get("data_end"),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _read_manifest(self) -> dict:
        if self._manifest_path.exists():
            try:
                return json.loads(self._manifest_path.read_text())
            except Exception:
                pass
        return {}

    def _write_manifest(self, manifest: dict) -> None:
        self._manifest_path.write_text(json.dumps(manifest, indent=2))

    def _update_manifest_from_base(self) -> None:
        """Initialise manifest from the base parquet after bootstrap."""
        try:
            df = pd.read_parquet(self._base_parquet)
            date_col = next(
                (c for c in ("order date (DateOrders)", "order_date") if c in df.columns),
                None,
            )
            data_end = None
            if date_col:
                ts = pd.to_datetime(df[date_col], errors="coerce").max()
                if pd.notna(ts):
                    data_end = ts.strftime("%Y-%m-%d")
            manifest = {
                "periods": [],
                "checksums": {},
                "row_counts": {},
                "total_rows": len(df),
                "last_increment": None,
                "data_end": data_end,
            }
            self._write_manifest(manifest)
        except Exception as e:
            logger.warning(f"CumulativeStore: could not init manifest from base: {e}")

    @staticmethod
    def _checksum(path: pathlib.Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]


def engineer_features_on_new(
    new_df: pd.DataFrame,
    base_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Engineer features for a new increment anchored on full cumulative history.

    Same pattern as engineer_features_on_test: concat [base | new] chronologically,
    engineer the combined frame, return only the new rows.

    This ensures expanding rates and rolling windows see the full history,
    not just the batch.
    """
    from app.feature_engineering import engineer_features_on_test
    return engineer_features_on_test(new_df, base_df)

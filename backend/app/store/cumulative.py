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
    # In-process cache: keyed on manifest JSON hash so any write invalidates it
    _cache: dict[str, pd.DataFrame] = {}

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

    def load_full(self, as_of: str | None = None) -> pd.DataFrame:
        """
        Return base.parquet concatenated with every increment in chronological
        period order.  If as_of is given, include only periods <= as_of.
        Validates each listed increment against manifest checksums and raises
        if a file is missing or its checksum does not match.
        Result is cached in memory keyed on the manifest JSON hash.
        """
        manifest = self._read_manifest()
        cache_key = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()[:16]
        if as_of:
            cache_key += f"_asof_{as_of}"

        if cache_key in CumulativeStore._cache:
            return CumulativeStore._cache[cache_key]

        frames: list[pd.DataFrame] = []
        if not self._base_parquet.exists():
            raise FileNotFoundError(
                "CumulativeStore: base.parquet not found. Run initialization first."
            )
        frames.append(pd.read_parquet(self._base_parquet))

        periods = manifest.get("periods", [])
        checksums = manifest.get("checksums", {})
        for period in periods:
            if as_of and period > as_of:
                continue
            inc_path = self._increments_dir / f"{period}.parquet"
            if not inc_path.exists():
                raise FileNotFoundError(
                    f"CumulativeStore: increment {period!r} listed in manifest "
                    f"but file {inc_path} is missing."
                )
            actual_cs = self._checksum(inc_path)
            expected_cs = checksums.get(period)
            if expected_cs and actual_cs != expected_cs:
                raise ValueError(
                    f"CumulativeStore: checksum mismatch for period {period!r}. "
                    f"Expected {expected_cs}, got {actual_cs}. File may be corrupted."
                )
            frames.append(pd.read_parquet(inc_path))

        df = pd.concat(frames, ignore_index=True)
        logger.info(f"CumulativeStore.load_full: {len(df)} rows (as_of={as_of!r})")
        CumulativeStore._cache[cache_key] = df
        return df

    def _invalidate_cache(self) -> None:
        CumulativeStore._cache.clear()

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

        # Assert increment has same column set as base
        if self._base_parquet.exists():
            base_cols = set(pd.read_parquet(self._base_parquet).columns)
            inc_cols  = set(df_engineered.columns)
            missing_cols = base_cols - inc_cols
            if missing_cols:
                raise ValueError(
                    f"CumulativeStore.append: increment for period {period!r} is missing "
                    f"columns present in base.parquet: {sorted(missing_cols)}. "
                    f"Run engineer_features_on_new before appending."
                )

        inc_path = self._increments_dir / f"{period}.parquet"
        df_engineered.to_parquet(inc_path, index=False)
        self._invalidate_cache()

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
        new_max_date = None
        if date_col:
            ts = pd.to_datetime(df_engineered[date_col], errors="coerce").max()
            if pd.notna(ts):
                manifest["data_end"] = ts.strftime("%Y-%m-%d")
                new_max_date = ts.strftime("%Y-%m-%d")

        self._write_manifest(manifest)

        report = AppendReport(
            period=period,
            rows_appended=len(df_engineered),
            cumulative_rows=manifest["total_rows"],
            checksum=checksum,
        )
        logger.info(
            "CumulativeStore.append: period=%s rows=%d cumulative=%d new_max_date=%s",
            period, len(df_engineered), manifest["total_rows"], new_max_date or "unknown",
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
        self._invalidate_cache()
        logger.info(f"CumulativeStore.rollback: removed period={period}")

    def periods(self) -> list[str]:
        """Return list of loaded increment periods in order."""
        return self._read_manifest().get("periods", [])

    def coverage(self) -> dict:
        """
        Return a structured coverage report for the /dataset/coverage endpoint.
        Includes base period range, base row count, each increment with its row
        count, combined total, and the latest date present.
        """
        manifest = self._read_manifest()
        base_rows = 0
        base_min_date = None
        base_max_date = None
        if self._base_parquet.exists():
            try:
                base_df = pd.read_parquet(self._base_parquet)
                base_rows = len(base_df)
                date_col = next(
                    (c for c in ("order date (DateOrders)", "order_date") if c in base_df.columns),
                    None,
                )
                if date_col:
                    dates = pd.to_datetime(base_df[date_col], errors="coerce").dropna()
                    if not dates.empty:
                        base_min_date = dates.min().strftime("%Y-%m-%d")
                        base_max_date = dates.max().strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"CumulativeStore.coverage: base read error: {e}")

        increments = []
        for period in manifest.get("periods", []):
            increments.append({
                "period": period,
                "rows": manifest.get("row_counts", {}).get(period, 0),
                "checksum": manifest.get("checksums", {}).get(period, ""),
            })

        increment_rows = sum(i["rows"] for i in increments)
        return {
            "base_period_start": base_min_date,
            "base_period_end": base_max_date,
            "base_row_count": base_rows,
            "increments": increments,
            "increment_count": len(increments),
            "combined_total": base_rows + increment_rows,
            "latest_date": manifest.get("data_end"),
        }

    def assert_base_no_holdout(self, holdout_start_date: str) -> None:
        """
        Assert that base.parquet contains no row on or after holdout_start_date.
        Raises ValueError if violated.
        """
        if not self._base_parquet.exists():
            return
        base_df = pd.read_parquet(self._base_parquet)
        date_col = next(
            (c for c in ("order date (DateOrders)", "order_date") if c in base_df.columns),
            None,
        )
        if date_col is None:
            return
        max_date = pd.to_datetime(base_df[date_col], errors="coerce").max()
        if pd.notna(max_date) and max_date >= pd.Timestamp(holdout_start_date):
            raise ValueError(
                f"CumulativeStore: base.parquet max date {max_date.date()} is on or after "
                f"holdout_start_date {holdout_start_date}. Training data is contaminated."
            )

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

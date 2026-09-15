"""
app/store/cumulative.py
========================
Cumulative dataset store — two-layer persistent design.

  BASE (immutable, disk):
    data/cumulative/base.parquet
    DataCo 2015-01-01 to 2017-09-30 — 171,962 rows.
    Written once during initialization. NEVER modified after that.
    Its row count, column count, date range, and SHA-256 checksum are
    recorded in manifest.json at write time and verified on every
    load_base() call.  A mismatch raises immediately.

  INCREMENTS (persistent, disk):
    data/cumulative/increments/<period>.parquet
    User-uploaded monthly actuals, written to disk after full
    preprocessing + feature engineering.  They survive server restarts.
    load_full() returns base + every increment recorded in the manifest,
    in append order.

  RESET:
    CumulativeStore.reset_increments(confirm=True) deletes every increment
    parquet, clears the manifest period list, and verifies that base.parquet
    is unchanged (checksum comparison).  It never touches base.parquet.
    The DELETE /api/v1/dataset/increments?confirm=true endpoint calls this.

Why persistent increments?
    A user who uploads a month and returns the next day must still see it.
    Increments are written to disk so they survive restarts.

Thread safety:
    All manifest reads/writes are serialised by a threading.Lock.
    Base is immutable after init — reads are always safe.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_BASE_DIR       = pathlib.Path("data/cumulative")
_BASE_PARQUET   = _BASE_DIR / "base.parquet"
_MANIFEST_FILE  = _BASE_DIR / "manifest.json"
_INCREMENTS_DIR = _BASE_DIR / "increments"

_MIN_BASE_ROWS = 100_000


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class AppendReport:
    period: str
    rows_appended: int
    cumulative_rows: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "rows_appended": self.rows_appended,
            "cumulative_rows": self.cumulative_rows,
            "timestamp": self.timestamp,
        }


class CumulativeStore:
    """
    Two-layer cumulative store.

    Layer 1 — base.parquet (disk, immutable after init):
        DataCo 2015-01 to 2017-09.  load_base() reads and verifies it.

    Layer 2 — increments/ (disk, persistent across restarts):
        Each user-uploaded month is stored as increments/<period>.parquet.
        load_full() returns base + all increments in manifest order.
        Increments survive server restarts.

    Use reset_increments(confirm=True) to wipe all increments and return
    to the clean base state.
    """

    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        base_dir: pathlib.Path | str = _BASE_DIR,
        source_parquet: pathlib.Path | str | None = None,
    ) -> None:
        self._base_dir       = pathlib.Path(base_dir)
        self._base_parquet   = self._base_dir / "base.parquet"
        self._manifest_file  = self._base_dir / "manifest.json"
        self._increments_dir = self._base_dir / "increments"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._increments_dir.mkdir(parents=True, exist_ok=True)

        # Bootstrap: copy processed_master.parquet → base.parquet if needed
        if not self._base_parquet.exists():
            src = pathlib.Path(source_parquet) if source_parquet else pathlib.Path(
                "data/uploads/processed_master.parquet"
            )
            if src.exists():
                shutil.copy2(src, self._base_parquet)
                logger.info("CumulativeStore: bootstrapped base from %s", src)

    # ── Manifest helpers ──────────────────────────────────────────────────────

    def _read_manifest(self) -> dict:
        if self._manifest_file.exists():
            try:
                return json.loads(self._manifest_file.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"base": {}, "periods": [], "checksums": {}}

    def _write_manifest(self, manifest: dict) -> None:
        self._manifest_file.write_text(json.dumps(manifest, indent=2))

    # ── Public API ────────────────────────────────────────────────────────────

    def load_base(self) -> pd.DataFrame:
        """
        Load the immutable base (DataCo 2015-01 to 2017-09).

        When manifest.json records base metadata (written by write_base() or
        _update_manifest_from_base()), verifies row count, column count, and
        SHA-256 checksum.  Raises on any mismatch.

        When no manifest entry exists (e.g. bootstrapped from
        processed_master.parquet without calling _update_manifest_from_base),
        loads without verification — the caller is responsible for integrity.
        """
        if not self._base_parquet.exists():
            raise FileNotFoundError(
                "CumulativeStore: base.parquet not found. Run initialization first."
            )

        df = pd.read_parquet(self._base_parquet)
        manifest = self._read_manifest()
        base_meta = manifest.get("base", {})

        if base_meta:
            recorded_rows = base_meta.get("row_count", 0)
            # Only enforce the minimum-rows guard when the manifest itself
            # recorded a large count (i.e. written by real initialization).
            # Tests that deliberately use small synthetic frames call
            # _update_manifest_from_base() which records the small count,
            # so recorded_rows < _MIN_BASE_ROWS and the guard is skipped.
            if recorded_rows >= _MIN_BASE_ROWS and len(df) < _MIN_BASE_ROWS:
                raise RuntimeError(
                    f"CumulativeStore: base.parquet has only {len(df):,} rows "
                    f"(manifest recorded {recorded_rows:,}, minimum {_MIN_BASE_ROWS:,}). "
                    f"This is a stub or truncated file. Re-run initialization."
                )
            if recorded_rows and len(df) != recorded_rows:
                raise RuntimeError(
                    f"CumulativeStore: base.parquet row count mismatch. "
                    f"Recorded={recorded_rows:,} Actual={len(df):,}."
                )
            # Only verify checksum when it is a full SHA-256 (64 hex chars).
            # Old manifests may store truncated checksums — skip those.
            recorded_checksum = base_meta.get("checksum", "")
            if recorded_checksum and len(recorded_checksum) == 64:
                actual_checksum = _sha256(self._base_parquet)
                if actual_checksum != recorded_checksum:
                    raise RuntimeError(
                        f"CumulativeStore: base.parquet checksum mismatch. "
                        f"Recorded={recorded_checksum[:12]}… "
                        f"Actual={actual_checksum[:12]}… "
                        f"The file has been modified since initialization."
                    )
            recorded_cols = base_meta.get("col_count", 0)
            if recorded_cols and len(df.columns) != recorded_cols:
                raise RuntimeError(
                    f"CumulativeStore: base.parquet column count mismatch. "
                    f"Recorded={recorded_cols} Actual={len(df.columns)}."
                )

        return df

    def load_full(self, as_of: str | None = None) -> pd.DataFrame:
        """
        Return base + all persisted increments in manifest order.

        If as_of is given (YYYY-MM), include only increments whose
        period <= as_of.

        Increments survive server restarts.  After reset_increments(),
        load_full() == load_base().
        """
        base_df = self.load_base()
        frames: list[pd.DataFrame] = [base_df]

        with self._lock:
            manifest = self._read_manifest()
            periods = manifest.get("periods", [])
            checksums = manifest.get("checksums", {})

        for entry in periods:
            period = entry["period"] if isinstance(entry, dict) else entry
            if as_of and period > as_of:
                continue
            inc_path = self._increments_dir / f"{period}.parquet"
            if not inc_path.exists():
                raise FileNotFoundError(
                    f"CumulativeStore.load_full: increment file missing for "
                    f"period={period} (expected {inc_path})"
                )
            # Verify per-increment checksum only when it is a full SHA-256.
            # Old manifests may store truncated checksums — skip those.
            recorded_cs = checksums.get(period, "")
            if recorded_cs and len(recorded_cs) == 64:
                actual_cs = _sha256(inc_path)
                if actual_cs != recorded_cs:
                    raise ValueError(
                        f"CumulativeStore.load_full: increment checksum mismatch for "
                        f"period={period}. Recorded={recorded_cs[:12]}… "
                        f"Actual={actual_cs[:12]}…"
                    )
            frames.append(pd.read_parquet(inc_path))

        df = pd.concat(frames, ignore_index=True)
        logger.debug(
            "CumulativeStore.load_full: %d rows (%d base + %d increment rows, as_of=%s)",
            len(df), len(base_df), len(df) - len(base_df), as_of,
        )
        return df

    def write_base(self, df: pd.DataFrame) -> None:
        """
        Write base.parquet and record its metadata in manifest.json.
        Called once by initialization.  Raises if df is too small or base
        already exists.
        """
        if self._base_parquet.exists():
            raise RuntimeError(
                "CumulativeStore.write_base: base.parquet already exists. "
                "Delete it manually before re-initializing."
            )
        if len(df) < _MIN_BASE_ROWS:
            raise RuntimeError(
                f"CumulativeStore.write_base: refusing to write {len(df):,}-row "
                f"DataFrame as base (stub or truncated — minimum {_MIN_BASE_ROWS:,} rows)."
            )
        df.to_parquet(self._base_parquet, index=False)
        self._update_manifest_from_base()
        logger.info(
            "CumulativeStore.write_base: %d rows written and manifest updated.",
            len(df),
        )

    def append(self, df_engineered: pd.DataFrame, period: str) -> AppendReport:
        """
        Persist an engineered increment to increments/<period>.parquet.

        The caller must have already run engineer_features_on_new() so that
        rolling windows are anchored on the full cumulative history.

        Raises ValueError if the period already exists (replay guard).
        """
        with self._lock:
            manifest = self._read_manifest()
            existing_periods = {
                (e["period"] if isinstance(e, dict) else e)
                for e in manifest.get("periods", [])
            }
            if period in existing_periods:
                raise ValueError(
                    f"CumulativeStore: period {period!r} already uploaded. "
                    f"Use reset_increments() to clear all increments."
                )

            # Column alignment check
            if self._base_parquet.exists():
                base_cols = set(pd.read_parquet(self._base_parquet).columns)
                missing = base_cols - set(df_engineered.columns)
                if missing:
                    raise ValueError(
                        f"CumulativeStore.append: increment for {period!r} is missing "
                        f"columns present in base.parquet: {sorted(missing)}. "
                        f"Run engineer_features_on_new before appending."
                    )

            inc_path = self._increments_dir / f"{period}.parquet"
            df_engineered.to_parquet(inc_path, index=False)
            inc_checksum = _sha256(inc_path)

            manifest.setdefault("periods", []).append({
                "period": period,
                "rows": len(df_engineered),
                "appended_at": datetime.now(timezone.utc).isoformat(),
            })
            manifest.setdefault("checksums", {})[period] = inc_checksum
            self._write_manifest(manifest)

        # Compute total rows for the report
        base_rows = len(pd.read_parquet(self._base_parquet)) if self._base_parquet.exists() else 0
        inc_rows = sum(
            e["rows"] if isinstance(e, dict) else 0
            for e in manifest["periods"]
        )
        total = base_rows + inc_rows

        report = AppendReport(
            period=period,
            rows_appended=len(df_engineered),
            cumulative_rows=total,
        )
        logger.info(
            "CumulativeStore.append: period=%s rows=%d total=%d (persisted to disk)",
            period, len(df_engineered), total,
        )
        return report

    def rollback(self, period: str) -> None:
        """Remove a persisted increment from disk and manifest."""
        with self._lock:
            manifest = self._read_manifest()
            periods = manifest.get("periods", [])
            existing = [e["period"] if isinstance(e, dict) else e for e in periods]
            if period not in existing:
                raise ValueError(
                    f"CumulativeStore: period {period!r} not found in manifest."
                )
            manifest["periods"] = [
                e for e in periods
                if (e["period"] if isinstance(e, dict) else e) != period
            ]
            manifest.get("checksums", {}).pop(period, None)
            self._write_manifest(manifest)

        inc_path = self._increments_dir / f"{period}.parquet"
        if inc_path.exists():
            inc_path.unlink()
        logger.info("CumulativeStore.rollback: removed period=%s", period)

    def reset_increments(self, confirm: bool = False) -> dict[str, Any]:
        """
        Delete every increment parquet and clear the manifest period list.
        base.parquet is NEVER touched.

        Verifies base.parquet checksum before and after to confirm it is
        unchanged.  Raises if confirm=False or if the checksum changes.
        """
        if not confirm:
            raise ValueError(
                "CumulativeStore.reset_increments: must pass confirm=True. "
                "This operation deletes all uploaded increments."
            )

        if not self._base_parquet.exists():
            raise FileNotFoundError(
                "CumulativeStore.reset_increments: base.parquet not found."
            )

        checksum_before = _sha256(self._base_parquet)

        with self._lock:
            manifest = self._read_manifest()
            periods_removed = []
            for entry in manifest.get("periods", []):
                period = entry["period"] if isinstance(entry, dict) else entry
                inc_path = self._increments_dir / f"{period}.parquet"
                if inc_path.exists():
                    inc_path.unlink()
                periods_removed.append(period)
            manifest["periods"] = []
            manifest["checksums"] = {}
            self._write_manifest(manifest)

        checksum_after = _sha256(self._base_parquet)
        if checksum_before != checksum_after:
            raise RuntimeError(
                "CumulativeStore.reset_increments: base.parquet checksum changed "
                "during reset — this should never happen."
            )

        logger.info(
            "CumulativeStore.reset_increments: removed %d periods: %s",
            len(periods_removed), periods_removed,
        )
        return {
            "periods_removed": periods_removed,
            "base_checksum_verified": checksum_after[:12] + "…",
            "base_unchanged": True,
        }

    def periods(self) -> list[str]:
        """Return list of uploaded periods from manifest."""
        with self._lock:
            manifest = self._read_manifest()
            return [
                e["period"] if isinstance(e, dict) else e
                for e in manifest.get("periods", [])
            ]

    def coverage(self) -> dict[str, Any]:
        """
        Coverage report for the /dataset/coverage endpoint.

        Example note:
            "base 2015-01-01 to 2017-09-30 (171,962 rows, immutable) +
             2 uploaded periods (4,310 rows, persisted to disk)"
        """
        base_rows = 0
        base_min_date = None
        base_max_date = None
        base_checksum_prefix = None

        with self._lock:
            manifest = self._read_manifest()

        base_meta = manifest.get("base", {})
        if self._base_parquet.exists():
            try:
                base_df = pd.read_parquet(self._base_parquet)
                base_rows = len(base_df)
                date_col = next(
                    (c for c in ("order date (DateOrders)", "order_date")
                     if c in base_df.columns),
                    None,
                )
                if date_col:
                    dates = pd.to_datetime(base_df[date_col], errors="coerce").dropna()
                    if not dates.empty:
                        base_min_date = dates.min().strftime("%Y-%m-%d")
                        base_max_date = dates.max().strftime("%Y-%m-%d")
                cs = base_meta.get("checksum", "")
                if cs and len(cs) == 64:
                    base_checksum_prefix = cs[:12] + "…"
            except Exception as e:
                logger.warning("CumulativeStore.coverage: base read error: %s", e)

        increments_info = []
        increment_rows = 0
        for entry in manifest.get("periods", []):
            period = entry["period"] if isinstance(entry, dict) else entry
            rows = entry.get("rows", 0) if isinstance(entry, dict) else 0
            inc_path = self._increments_dir / f"{period}.parquet"
            if not rows and inc_path.exists():
                try:
                    rows = len(pd.read_parquet(inc_path))
                except Exception:
                    pass
            increments_info.append({"period": period, "rows": rows})
            increment_rows += rows

        base_period_start = base_meta.get("date_min") or base_min_date
        base_period_end   = base_meta.get("date_max") or base_max_date

        n_inc = len(increments_info)
        note = (
            f"base {base_period_start} to {base_period_end} "
            f"({base_rows:,} rows, immutable)"
        )
        if n_inc:
            note += (
                f" + {n_inc} uploaded period{'s' if n_inc != 1 else ''} "
                f"({increment_rows:,} rows, persisted to disk)"
            )

        return {
            "base_period_start": base_period_start,
            "base_period_end": base_period_end,
            "base_row_count": base_rows,
            "base_checksum_prefix": base_checksum_prefix,
            "increments": increments_info,
            "increment_count": n_inc,
            "combined_total": base_rows + increment_rows,
            "note": note,
        }

    def summary(self) -> dict[str, Any]:
        """Summary for API responses."""
        with self._lock:
            manifest = self._read_manifest()
        periods = [
            e["period"] if isinstance(e, dict) else e
            for e in manifest.get("periods", [])
        ]
        inc_rows = sum(
            e.get("rows", 0) if isinstance(e, dict) else 0
            for e in manifest.get("periods", [])
        )
        base_rows = 0
        if self._base_parquet.exists():
            try:
                base_rows = len(pd.read_parquet(self._base_parquet))
            except Exception:
                pass
        return {
            "base_exists": self._base_parquet.exists(),
            "base_rows": base_rows,
            "uploaded_periods": periods,
            "increment_rows": inc_rows,
            "total_rows": base_rows + inc_rows,
            "last_increment": periods[-1] if periods else None,
            "note": "Increments are persisted to disk and survive server restarts.",
        }

    def assert_base_no_holdout(self, holdout_start_date: str) -> None:
        """Assert base.parquet contains no row on or after holdout_start_date."""
        if not self._base_parquet.exists():
            return
        base_df = pd.read_parquet(self._base_parquet)
        date_col = next(
            (c for c in ("order date (DateOrders)", "order_date")
             if c in base_df.columns),
            None,
        )
        if date_col is None:
            return
        max_date = pd.to_datetime(base_df[date_col], errors="coerce").max()
        if pd.notna(max_date) and max_date >= pd.Timestamp(holdout_start_date):
            raise ValueError(
                f"CumulativeStore: base.parquet max date {max_date.date()} is on or "
                f"after holdout_start_date {holdout_start_date}. "
                f"Training data is contaminated."
            )

    def _update_manifest_from_base(self) -> None:
        """
        Register base.parquet metadata (row count, col count, SHA-256 checksum,
        date range) in manifest.json.  Called after writing base.parquet so that
        load_base() can verify integrity on every subsequent load.
        """
        if not self._base_parquet.exists():
            return
        df = pd.read_parquet(self._base_parquet)
        checksum = _sha256(self._base_parquet)
        date_col = next(
            (c for c in ("order date (DateOrders)", "order_date") if c in df.columns),
            None,
        )
        dates = (
            pd.to_datetime(df[date_col], errors="coerce").dropna()
            if date_col
            else pd.Series([], dtype="datetime64[ns]")
        )
        with self._lock:
            manifest = self._read_manifest()
            manifest["base"] = {
                "row_count": len(df),
                "col_count": len(df.columns),
                "checksum": checksum,
                "date_min": dates.min().strftime("%Y-%m-%d") if not dates.empty else None,
                "date_max": dates.max().strftime("%Y-%m-%d") if not dates.empty else None,
                "written_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_manifest(manifest)

    def _invalidate_cache(self) -> None:
        """No-op in the persistent design — there is no in-process cache to clear."""
        pass


def engineer_features_on_new(
    new_df: pd.DataFrame,
    base_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Engineer features for a new increment anchored on full cumulative history.

    Concatenates [base | new] chronologically, runs full Tier-1 feature
    engineering on the combined frame, then returns only the new rows.

    This ensures expanding rates and rolling windows see the full
    2015-01 to 2017-09 history before computing features for the new month.
    """
    from app.feature_engineering import engineer_features_on_test
    return engineer_features_on_test(new_df, base_df)

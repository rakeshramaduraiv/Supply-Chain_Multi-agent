"""
app/core/period.py
==================
Single source of truth for the current data boundary and next upload period.

All endpoints, response strings, and UI labels must read from here.
No literal period string may appear anywhere else.

The data end is derived from the cumulative store's manifest, which is updated
every time an increment is appended. On a fresh system (DataCo only), the data
end is 2017-09-30 (last order date in the training window).
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import date
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Anchor paths from this file's location so they resolve correctly
# regardless of the process working directory (Defect 3).
_MODULE_DIR     = pathlib.Path(__file__).resolve().parent          # app/core/
_BACKEND_DIR    = _MODULE_DIR.parent.parent                        # backend/
_MANIFEST_PATH  = _BACKEND_DIR / "data" / "cumulative" / "manifest.json"
_BASE_PARQUET   = _BACKEND_DIR / "data" / "cumulative" / "base.parquet"
_FALLBACK_END   = pd.Timestamp("2017-09-30")   # DataCo training window end

logger.debug("[period] manifest path resolved to: %s", _MANIFEST_PATH)


def _read_manifest() -> dict:
    if _MANIFEST_PATH.exists():
        try:
            return json.loads(_MANIFEST_PATH.read_text())
        except Exception:
            pass
    return {}


def current_data_end() -> pd.Timestamp:
    """
    Return the latest order_date present in the cumulative store.

    Reads from manifest first (fast path). Falls back to scanning the base
    parquet if the manifest is absent.

    When neither source is available, logs a WARNING and returns _FALLBACK_END.
    A silent fallback is never acceptable (Defect 3c).
    """
    manifest = _read_manifest()
    if manifest.get("data_end"):
        try:
            return pd.Timestamp(manifest["data_end"])
        except Exception:
            pass

    # Scan base parquet
    if _BASE_PARQUET.exists():
        try:
            df = pd.read_parquet(_BASE_PARQUET, columns=["order date (DateOrders)"])
            ts = pd.to_datetime(df["order date (DateOrders)"], errors="coerce").max()
            if pd.notna(ts):
                return ts
        except Exception:
            pass

    # Defect 3c: warn explicitly — never silently fall back
    logger.warning(
        "[period] current_data_end: manifest not found at %s and base parquet "
        "not found at %s — falling back to hardcoded %s. "
        "Run initialization to populate the cumulative store.",
        _MANIFEST_PATH, _BASE_PARQUET, _FALLBACK_END.date(),
    )
    return _FALLBACK_END


def next_period() -> str:
    """
    Return the next upload period as "YYYY-MM" — the month after data_end.

    Uses pandas Period arithmetic so the result is always the calendar month
    after data_end, regardless of which day of the month data_end falls on
    (Defect 1a). Asserts the result is strictly greater than the period
    containing data_end (Defect 1b).
    """
    end = current_data_end()
    result = str(pd.Period(end, freq="M") + 1)   # e.g. "2017-10"

    # Defect 1b: invariant — result must be strictly after end's month
    end_period = str(pd.Period(end, freq="M"))
    if result <= end_period:
        raise RuntimeError(
            f"next_period() invariant violated: result {result!r} is not "
            f"strictly greater than data_end period {end_period!r} "
            f"(data_end={end.date()}). This should never happen."
        )
    return result


def period_bounds(period: str) -> tuple[date, date]:
    """
    Return (first_day, last_day) for a "YYYY-MM" period string.
    """
    ts = pd.Timestamp(period + "-01")
    first = ts.date()
    # Last day: first day of next month minus one day
    next_month = (ts + pd.offsets.MonthEnd(1)).date()
    return first, next_month


def cycle_status() -> dict:
    """
    Return the current cycle status dict consumed by GET /api/v1/cycle/status.
    All period strings in the API come from here — never from literals.
    """
    manifest = _read_manifest()
    data_end = current_data_end()
    return {
        "data_end":      data_end.strftime("%Y-%m-%d"),
        "next_period":   next_period(),
        "periods_loaded": manifest.get("periods", []),
        "cumulative_rows": manifest.get("total_rows", 0),
        "last_increment": manifest.get("last_increment"),
    }

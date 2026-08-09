"""
app/core/period.py
==================
Single source of truth for the current data boundary and next upload period.

All endpoints, response strings, and UI labels must read from here.
No literal period string ("2019-01", "February 2019") may appear anywhere else.

The data end is derived from the cumulative store's manifest, which is updated
every time an increment is appended. On a fresh system (DataCo only), the data
end is 2018-01-31 (last order date in DataCoSupplyChainDataset.csv).
"""

from __future__ import annotations

import json
import pathlib
from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

_MANIFEST_PATH = pathlib.Path("data/cumulative/manifest.json")
_BASE_PARQUET   = pathlib.Path("data/cumulative/base.parquet")
_FALLBACK_END   = pd.Timestamp("2018-01-31")   # last real DataCo row


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
    parquet if the manifest is absent. Returns _FALLBACK_END if neither exists.
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

    return _FALLBACK_END


def next_period() -> str:
    """
    Return the next upload period as "YYYY-MM" — the month after data_end.

    Example: data_end=2018-01-31 → "2018-02"
    """
    end = current_data_end()
    first_of_next = (end + timedelta(days=1)).replace(day=1)
    return first_of_next.strftime("%Y-%m")


def period_bounds(period: str) -> tuple[date, date]:
    """
    Return (first_day, last_day) for a "YYYY-MM" period string.

    Example: "2018-02" → (date(2018,2,1), date(2018,2,28))
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

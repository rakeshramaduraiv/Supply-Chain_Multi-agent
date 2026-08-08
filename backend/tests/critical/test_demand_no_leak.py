"""
Regression test: demand_spike_flag and qty_roll_7 must not correlate
strongly with the demand target (Order Item Quantity).

demand_spike_flag: corrected to use qty_prev (shifted) — must be < 0.30
qty_roll_7:        shifted rolling mean — autocorrelation is real signal,
                   but must stay below 0.60 (a full-df leak would be ~0.99)
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
import pytest
from app.feature_engineering import engineer_features

TARGET = "Order Item Quantity"
RAW_PARQUET = pathlib.Path("data/uploads/processed_master.parquet")
RAW_CSV     = pathlib.Path("data/raw/DataCoSupplyChainDataset.csv")


@pytest.fixture(scope="module")
def engineered_df():
    """Always re-engineer from source so rolling features reflect current code."""
    if RAW_CSV.exists():
        df = pd.read_csv(RAW_CSV, encoding="latin-1")
        return engineer_features(df)
    elif RAW_PARQUET.exists():
        # Re-engineer even if columns exist — parquet may be pre-fix
        df = pd.read_parquet(RAW_PARQUET)
        return engineer_features(df)
    else:
        pytest.skip("No source data available")


def _corr(a: pd.Series, b: pd.Series) -> float:
    mask = a.notna() & b.notna()
    return float(np.corrcoef(a[mask].astype(float), b[mask].astype(float))[0, 1])


def test_demand_spike_flag_not_leaky(engineered_df):
    df = engineered_df
    assert "demand_spike_flag" in df.columns, "demand_spike_flag missing"
    assert TARGET in df.columns, f"{TARGET} missing"
    corr = abs(_corr(df["demand_spike_flag"], df[TARGET]))
    assert corr < 0.30, (
        f"demand_spike_flag correlates {corr:.4f} with {TARGET} — "
        f"current-row leak not fixed (threshold 0.30)"
    )


def test_qty_roll_7_not_leaky(engineered_df):
    df = engineered_df
    assert "qty_roll_7" in df.columns, "qty_roll_7 missing"
    assert TARGET in df.columns, f"{TARGET} missing"
    corr = abs(_corr(df["qty_roll_7"], df[TARGET]))
    assert corr < 0.75, (
        f"qty_roll_7 correlates {corr:.4f} with {TARGET} — "
        f"full-df leak would be ~0.99; threshold 0.75"
    )

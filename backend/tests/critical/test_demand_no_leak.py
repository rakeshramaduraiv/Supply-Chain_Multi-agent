"""
tests/critical/test_demand_no_leak.py

Asserts that DEMAND_FEATURES produce test R2 < 0.55 on a chronological split.
An R2 >= 0.55 means an algebraic leak is still present.
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score

from app.ml.utils import DEMAND_FEATURES, DEMAND_TARGET, chronological_split
from app.feature_engineering import engineer_features

PARQUET = Path("data/uploads/processed_master.parquet")
CSV     = Path("data/raw/DataCoSupplyChainDataset.csv")

_MAX_R2 = 0.55


def _load_engineered() -> pd.DataFrame:
    if PARQUET.exists():
        return pd.read_parquet(PARQUET)
    if CSV.exists():
        df = pd.read_csv(CSV, encoding="latin-1")
        date_col = "order date (DateOrders)"
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.sort_values(date_col).reset_index(drop=True)
        return engineer_features(df)
    pytest.skip("No dataset available")


def test_demand_r2_below_leak_threshold():
    df = _load_engineered()
    train_df, test_df = chronological_split(df, train_ratio=0.8)

    available_train = [f for f in DEMAND_FEATURES if f in train_df.columns]
    available_test  = [f for f in DEMAND_FEATURES if f in test_df.columns]
    features = list(set(available_train) & set(available_test))

    assert DEMAND_TARGET in train_df.columns, f"Target '{DEMAND_TARGET}' missing"

    X_train = train_df[features].fillna(0)
    y_train = train_df[DEMAND_TARGET]
    X_test  = test_df[features].fillna(0)
    y_test  = test_df[DEMAND_TARGET]

    model = HistGradientBoostingRegressor(max_iter=200, random_state=42)
    model.fit(X_train, y_train)
    r2 = r2_score(y_test, model.predict(X_test))

    print(f"\nDemand test R2 = {r2:.4f} (threshold < {_MAX_R2})")
    assert r2 < _MAX_R2, (
        f"Demand R2={r2:.4f} >= {_MAX_R2}. "
        f"An algebraic leak is still present in DEMAND_FEATURES. "
        f"Run leave-one-out ablation to identify the leaky feature."
    )

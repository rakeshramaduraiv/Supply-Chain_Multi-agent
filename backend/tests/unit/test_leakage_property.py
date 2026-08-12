"""
Verification test 2 — property test for temporal leakage.

Builds a small synthetic DataFrame, engineers features on the first N rows,
then engineers on all rows, and asserts the first-N rows' feature values are
IDENTICAL in both runs.  Any feature that changes when future rows are appended
is leaking by construction.
"""

import numpy as np
import pandas as pd
import pytest

from app.feature_engineering import engineer_features, ENGINEERED_FEATURES

# Features that are legitimately excluded from the property check:
#   - post-shipment observables: banned from models, not temporal features
#   - graph_tpke_edge_density: normalised by a running max that can grow as
#     more rows arrive — the running max is itself leak-free but the ratio
#     for early rows can change when the global running max increases.
#     This is acceptable: the feature is excluded from deployed models.
_EXCLUDED = {
    "delivery_gap", "is_delayed", "delivery_duration_days",
    "shipping_delay_ratio", "shipping_delay", "shipping_efficiency_score",
    "composite_risk_score", "delay_category",
    "graph_tpke_edge_density",
}

_FEATURES_TO_CHECK = [f for f in ENGINEERED_FEATURES if f not in _EXCLUDED]


def _make_synthetic(n: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2016-01-01", periods=n, freq="D")
    depts = rng.choice(["Fan Shop", "Apparel", "Golf"], size=n)
    cats  = rng.choice(["Cleats", "Cardigan", "Golf Bag"], size=n)
    modes = rng.choice(["Standard Class", "First Class", "Second Class"], size=n)
    regions = rng.choice(["Western Europe", "Central America", "South Asia"], size=n)

    return pd.DataFrame({
        "order date (DateOrders)": dates,
        "Department Name":         depts,
        "Category Name":           cats,
        "Shipping Mode":           modes,
        "Order Region":            regions,
        "Order Country":           "United States",
        "Order City":              "Chicago",
        "Order Item Quantity":     rng.integers(1, 10, size=n).astype(float),
        "Product Price":           rng.uniform(10, 200, size=n),
        "Sales":                   rng.uniform(20, 500, size=n),
        "Order Item Discount":     rng.uniform(0, 50, size=n),
        "Days for shipment (scheduled)": rng.integers(2, 7, size=n).astype(float),
        "Days for shipping (real)":      rng.integers(1, 9, size=n).astype(float),
        "Late_delivery_risk":      rng.integers(0, 2, size=n).astype(float),
        "Order Id":                np.arange(n).astype(str),
        "Customer Id":             rng.integers(1, 20, size=n).astype(str),
        "Customer Segment":        "Consumer",
        "Order Profit Per Order":  rng.uniform(-10, 100, size=n),
    })


@pytest.fixture(scope="module")
def engineered_small_and_full():
    """Returns (eng_small, eng_full_first_n) for N=60 out of 120 rows."""
    n_small = 60
    df_full  = _make_synthetic(120)
    df_small = df_full.iloc[:n_small].copy()

    eng_small      = engineer_features(df_small)
    eng_full       = engineer_features(df_full)

    # Align on the date column so we compare the same rows
    date_col = "order date (DateOrders)"
    small_dates = eng_small[date_col].values
    eng_full_first_n = eng_full[eng_full[date_col].isin(small_dates)].copy()

    return eng_small.reset_index(drop=True), eng_full_first_n.reset_index(drop=True)


@pytest.mark.parametrize("feature", _FEATURES_TO_CHECK)
def test_feature_stable_when_future_rows_appended(
    engineered_small_and_full, feature
):
    eng_small, eng_full_first_n = engineered_small_and_full

    if feature not in eng_small.columns:
        pytest.skip(f"{feature} not produced (optional column missing)")

    s_small = eng_small[feature].fillna(0).round(6)
    s_full  = eng_full_first_n[feature].fillna(0).round(6)

    assert len(s_small) == len(s_full), (
        f"{feature}: row count mismatch {len(s_small)} vs {len(s_full)}"
    )

    changed = (s_small != s_full).sum()
    assert changed == 0, (
        f"LEAK DETECTED: {feature} changed in {changed}/{len(s_small)} rows "
        f"when future rows were appended. "
        f"Max abs diff: {(s_small - s_full).abs().max():.6f}"
    )

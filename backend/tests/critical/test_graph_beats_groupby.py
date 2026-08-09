"""
test_graph_beats_groupby.py
============================
For each graph_* feature in the regenerated parquet, compute the plain pandas
groupby equivalent and assert corr(enriched, groupby_equivalent) < 0.95.

If the correlation is >= 0.95, the graph traversal contributed nothing that a
groupby could not — the test fails and names the offending pair.

This is the check that would have caught:
  - commit 38ff04e: pandas fallback in enrichment (groupby in disguise)
  - commit e809c1a: groupby stored in node, fetched back (round-trip)

Skipped when processed_master.parquet is absent or < 100k rows (stub).
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

_PARQUET = Path(__file__).parents[2] / "data" / "uploads" / "processed_master.parquet"
_MIN_ROWS = 100_000

pytestmark = pytest.mark.skipif(
    not _PARQUET.exists() or (
        _PARQUET.exists() and len(pd.read_parquet(_PARQUET, columns=["Late_delivery_risk"])) < _MIN_ROWS
    ),
    reason="processed_master.parquet absent or stub — skipped until real initialization runs",
)


@pytest.fixture(scope="module")
def df():
    return pd.read_parquet(_PARQUET)


def _corr(a: pd.Series, b: pd.Series) -> float:
    """Pearson correlation, handling constant series."""
    if a.std() < 1e-9 or b.std() < 1e-9:
        return 1.0  # constant vs anything is degenerate — treat as correlated
    return float(a.corr(b))


# ── graph_supplier_reliability ────────────────────────────────────────────────

def test_supplier_reliability_differs_from_groupby(df):
    """
    Groupby equivalent: mean(reliability_score) per (dept, cat, region).
    The enriched value blends in peers from different dept OR different category,
    so it must diverge from the pure within-group mean.
    """
    dept_col = "Department Name"
    cat_col  = "Category Name"
    reg_col  = "Order Region"
    rel_col  = "supplier_reliability_score"
    target   = "graph_supplier_reliability"

    required = [dept_col, cat_col, reg_col, rel_col, target]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        pytest.skip(f"Missing columns: {missing}")

    groupby_equiv = (
        df.groupby([dept_col, cat_col, reg_col])[rel_col]
        .transform("mean")
    )

    corr = _corr(df[target], groupby_equiv)
    assert corr < 0.95, (
        f"graph_supplier_reliability correlates {corr:.4f} with its pandas groupby "
        f"equivalent (dept|cat|region mean of reliability_score). "
        f"The graph traversal contributed nothing. "
        f"Verify :SIMILAR_TO edges exist and _Q_SUPPLIER walks them."
    )


# ── graph_avg_shipping_delay ──────────────────────────────────────────────────

def test_shipping_delay_differs_from_groupby(df):
    """
    Groupby equivalent: mean(shipping_delay) per (mode, region, country).
    The enriched value blends in peers from different shipping_mode (same region),
    so it must diverge from the pure within-group mean.
    """
    mode_col    = "Shipping Mode"
    reg_col     = "Order Region"
    country_col = "Order Country"
    delay_col   = "shipping_delay"
    target      = "graph_avg_shipping_delay"

    required = [mode_col, reg_col, country_col, delay_col, target]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        pytest.skip(f"Missing columns: {missing}")

    groupby_equiv = (
        df.groupby([mode_col, reg_col, country_col])[delay_col]
        .transform("mean")
    )

    corr = _corr(df[target], groupby_equiv)
    assert corr < 0.95, (
        f"graph_avg_shipping_delay correlates {corr:.4f} with its pandas groupby "
        f"equivalent (mode|region|country mean of shipping_delay). "
        f"The graph traversal contributed nothing. "
        f"Verify :SHARES_LANE edges exist and _Q_SHIPPING walks them."
    )


# ── graph_inventory_stress ────────────────────────────────────────────────────

def test_inventory_stress_differs_from_groupby(df):
    """
    Groupby equivalent: mean(inventory_stress_index) per (cat, region).
    The enriched value blends in peers from different region (same category),
    so it must diverge from the pure within-group mean.
    """
    cat_col    = "Category Name"
    reg_col    = "Order Region"
    stress_col = "inventory_stress_index"
    target     = "graph_inventory_stress"

    required = [cat_col, reg_col, stress_col, target]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        pytest.skip(f"Missing columns: {missing}")

    groupby_equiv = (
        df.groupby([cat_col, reg_col])[stress_col]
        .transform("mean")
    )

    corr = _corr(df[target], groupby_equiv)
    assert corr < 0.95, (
        f"graph_inventory_stress correlates {corr:.4f} with its pandas groupby "
        f"equivalent (cat|region mean of inventory_stress_index). "
        f"The graph traversal contributed nothing. "
        f"Verify :SAME_CATEGORY edges exist and _Q_INVENTORY walks them."
    )


# ── Peer edges must exist ─────────────────────────────────────────────────────

def test_peer_edge_counts_nonzero(df):
    """
    Indirect check: if the graph contributed something, the enriched values
    must differ from the anchor-only groupby. This test checks that at least
    one of the three features passes the < 0.95 threshold, confirming that
    build_peer_edges() ran and produced edges.
    """
    results = {}

    for feat, key_cols, raw_col in [
        ("graph_supplier_reliability",
         ["Department Name", "Category Name", "Order Region"],
         "supplier_reliability_score"),
        ("graph_avg_shipping_delay",
         ["Shipping Mode", "Order Region", "Order Country"],
         "shipping_delay"),
        ("graph_inventory_stress",
         ["Category Name", "Order Region"],
         "inventory_stress_index"),
    ]:
        if feat not in df.columns or raw_col not in df.columns:
            continue
        if not all(c in df.columns for c in key_cols):
            continue
        groupby_equiv = df.groupby(key_cols)[raw_col].transform("mean")
        results[feat] = _corr(df[feat], groupby_equiv)

    if not results:
        pytest.skip("No graph_* features present in parquet")

    all_high = all(c >= 0.95 for c in results.values())
    assert not all_high, (
        f"All graph_* features correlate >= 0.95 with their pandas groupby equivalents: "
        f"{results}. "
        f"build_peer_edges() either did not run or produced no edges. "
        f"Re-run initialization with Neo4j available."
    )

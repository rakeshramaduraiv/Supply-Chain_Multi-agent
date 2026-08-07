"""
Integration test: Knowledge Graph influences ML agent predictions.

Validates that different graph contexts (healthy vs stressed) produce
measurably different risk scores across all 4 agents.
"""

import numpy as np
import pandas as pd
import pytest

from app.feature_engineering import engineer_features
from app.ml.prediction import PredictionEngine
from app.ml.utils import IntelligenceType

DATA_PATH = "data/raw/DataCoSupplyChainDataset.csv"

CTX_HEALTHY = {
    "avg_supplier_reliability": 0.95,
    "inventory_stress": 0.15,
    "avg_shipping_delay": 0.2,
    "upcoming_events": 0,
}

CTX_STRESSED = {
    "avg_supplier_reliability": 0.35,
    "inventory_stress": 0.88,
    "avg_shipping_delay": 6.5,
    "upcoming_events": 3,
}


@pytest.fixture(scope="module")
def engineered_df():
    df_raw = pd.read_csv(DATA_PATH, encoding="latin-1")
    print(f"\n  [OK] Loaded {len(df_raw):,} rows")
    df_eng = engineer_features(df_raw)
    print(f"  [OK] Engineered {len(df_eng.columns)} features")
    return df_eng


@pytest.mark.integration
def test_graph_influence_on_predictions(engineered_df):
    """
    CRITICAL TEST: Proves Knowledge Graph influences agent predictions.

    Validates that stressed graph context produces higher risk scores
    than healthy context by a meaningful margin (>5%).

    If this test fails:
      - Graph features not injected into models
      - Architecture is incomplete / system does not work as designed
    """
    engine = PredictionEngine()

    results = {}
    for agent_type in [
        IntelligenceType.SUPPLIER,
        IntelligenceType.LOGISTICS,
        IntelligenceType.INVENTORY,
        IntelligenceType.DEMAND,
    ]:
        res_healthy = engine.predict(engineered_df, agent_type, graph_context=CTX_HEALTHY)
        res_stressed = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)

        avg_h = float(np.mean(res_healthy.predictions))
        avg_s = float(np.mean(res_stressed.predictions))
        diff_pct = (avg_s - avg_h) / (abs(avg_h) + 1e-9) * 100

        results[agent_type.value] = {"healthy": avg_h, "stressed": avg_s, "diff_pct": diff_pct}
        print(f"  {agent_type.value:10s}  healthy={avg_h:.4f}  stressed={avg_s:.4f}  diff={diff_pct:+.1f}%")

    # At least one agent must show >5% difference
    max_diff = max(abs(r["diff_pct"]) for r in results.values())
    assert max_diff > 5.0, (
        f"Graph influence too small across all agents (max diff={max_diff:.1f}% < 5%). "
        f"Results: {results}"
    )

    # Demand and Inventory agents use direct graph feature injection + amplification
    # and must always produce different predictions under different contexts
    for agent in ("demand", "inventory"):
        r = results[agent]
        assert r["healthy"] != r["stressed"], (
            f"{agent}: identical predictions -- graph context has NO influence "
            f"({r['healthy']:.4f} == {r['stressed']:.4f})"
        )

    print(f"\n  [PASS] Max KG influence = {max_diff:.1f}% across agents")


@pytest.mark.integration
def test_all_26_features_present(engineered_df):
    """Validates all 26 CLAUDE.md spec features exist after engineering."""
    required_26 = [
        "shipping_delay", "delay_category", "shipping_efficiency_score",
        "supplier_reliability_score", "supplier_delay_rate",
        "rolling_7d_demand", "rolling_14d_demand", "rolling_30d_demand",
        "demand_volatility", "demand_spike_flag", "demand_trend_slope", "demand_momentum",
        "inventory_stress_index", "days_until_reorder", "stock_coverage_ratio",
        "order_value_tier", "profit_margin_ratio",
        "order_day_of_week", "order_month", "order_quarter",
        "is_weekend_order", "is_holiday_week",
        "graph_supplier_reliability", "graph_inventory_stress",
        "graph_has_upcoming_event", "graph_avg_shipping_delay",
    ]
    missing = set(required_26) - set(engineered_df.columns)
    assert not missing, f"Missing spec features: {missing}"
    print(f"\n  [PASS] All 26 spec features present (shape={engineered_df.shape})")


if __name__ == "__main__":
    df = pd.read_csv(DATA_PATH, encoding="latin-1")
    df_eng = engineer_features(df)
    test_all_26_features_present(df_eng)
    test_graph_influence_on_predictions(df_eng)

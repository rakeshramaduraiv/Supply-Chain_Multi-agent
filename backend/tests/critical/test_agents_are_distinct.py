"""
Critical test — No agent pair correlates > 0.95 (§8.1 Gate 4).

Supplier and Logistics sharing byte-identical metrics is a sign they are the
same model. This test catches that after training.
"""

import numpy as np
import pandas as pd
import pytest

from app.feature_engineering import engineer_features
from app.ml.prediction import PredictionEngine
from app.ml.utils import IntelligenceType, assert_agents_distinct

DATA_PATH = "data/raw/DataCoSupplyChainDataset.csv"

CTX_NEUTRAL = {
    "avg_supplier_reliability": 0.7,
    "inventory_stress":         0.4,
    "avg_shipping_delay":       2.0,
    "upcoming_events":          [],
    "holiday_risk_events":      [],
    "amplified_supplier_count": 0,
    "demand_volatility":        0.3,
    "demand_trend_slope":       0.0,
}


@pytest.fixture(scope="module")
def engineered_df():
    df_raw = pd.read_csv(DATA_PATH, encoding="latin-1")
    return engineer_features(df_raw)


@pytest.fixture(scope="module")
def agent_predictions(engineered_df):
    engine = PredictionEngine()
    preds = {}
    for agent_type in [IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS,
                       IntelligenceType.INVENTORY]:
        result = engine.predict(engineered_df, agent_type, graph_context=CTX_NEUTRAL)
        preds[agent_type.value] = np.array(
            result.probabilities if result.probabilities else result.predictions
        )
    return preds


class TestAgentsAreDistinct:

    def test_supplier_logistics_not_identical(self, agent_predictions):
        """
        Supplier and Logistics must not produce identical predictions.
        Identical metrics (accuracy 0.971776 for both) is the leakage signature.
        """
        s = agent_predictions["supplier"]
        l = agent_predictions["logistics"]
        r = float(np.corrcoef(s, l)[0, 1])
        assert r < 0.95, (
            f"Supplier and Logistics predictions correlate at {r:.3f} >= 0.95. "
            f"They are effectively the same model. "
            f"Differentiate by feature emphasis (supplier history vs route/region)."
        )
        print(f"\n  supplier-logistics correlation: {r:.4f}  [PASS]")

    def test_all_pairs_distinct(self, agent_predictions):
        """assert_agents_distinct raises on any pair > 0.95."""
        try:
            assert_agents_distinct(agent_predictions, threshold=0.95)
        except ValueError as e:
            pytest.fail(str(e))

    def test_supplier_predictions_not_constant(self, agent_predictions):
        s = agent_predictions["supplier"]
        assert s.std() > 0.01, (
            f"Supplier predictions are nearly constant (std={s.std():.4f}). "
            f"Model may have collapsed to predicting the majority class."
        )

    def test_logistics_predictions_not_constant(self, agent_predictions):
        l = agent_predictions["logistics"]
        assert l.std() > 0.01, (
            f"Logistics predictions are nearly constant (std={l.std():.4f})."
        )

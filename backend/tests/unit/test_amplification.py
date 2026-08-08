"""
Unit tests — Amplification Integrity (spec §4, Invariant 4).

Gate 4: Classifier amplification operates on probabilities; labels ∈ {0,1}.

Verifies:
  - predictions list contains only 0 or 1 for classifiers
  - probabilities list is in [0.0, 1.0]
  - stressed context produces higher mean probability than healthy context
  - risk_levels are consistent with probabilities
  - regressor predictions are finite positive floats (not clipped to {0,1})
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
    "inventory_stress":         0.15,
    "avg_shipping_delay":       0.2,
    "upcoming_events":          [],
    "holiday_risk_events":      [],
    "amplified_supplier_count": 0,
    "demand_volatility":        0.1,
    "demand_trend_slope":       0.0,
}

CTX_STRESSED = {
    "avg_supplier_reliability": 0.35,
    "inventory_stress":         0.88,
    "avg_shipping_delay":       6.5,
    "upcoming_events":          ["Black Friday", "Cyber Monday", "Christmas"],
    "holiday_risk_events":      ["SEASONAL_STOCKOUT_RISK"],
    "amplified_supplier_count": 2,
    "demand_volatility":        0.8,
    "demand_trend_slope":       1.5,
}

VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
CLASSIFIER_AGENTS = [
    IntelligenceType.SUPPLIER,
    IntelligenceType.LOGISTICS,
    IntelligenceType.INVENTORY,
]


@pytest.fixture(scope="module")
def engineered_df():
    df_raw = pd.read_csv(DATA_PATH, encoding="latin-1")
    return engineer_features(df_raw)


@pytest.fixture(scope="module")
def engine():
    return PredictionEngine()


class TestClassifierLabels:
    """Invariant 4a: classifier predictions must be binary {0, 1}."""

    @pytest.mark.parametrize("agent_type", CLASSIFIER_AGENTS)
    def test_predictions_are_binary_healthy(self, engineered_df, engine, agent_type):
        result = engine.predict(engineered_df, agent_type, graph_context=CTX_HEALTHY)
        invalid = [p for p in result.predictions if p not in (0, 1)]
        assert not invalid, (
            f"Invariant 4 VIOLATED: {agent_type.value} predictions contain non-binary values "
            f"under healthy context: {invalid[:5]}. "
            f"Amplification must operate on probabilities, not labels."
        )

    @pytest.mark.parametrize("agent_type", CLASSIFIER_AGENTS)
    def test_predictions_are_binary_stressed(self, engineered_df, engine, agent_type):
        result = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)
        invalid = [p for p in result.predictions if p not in (0, 1)]
        assert not invalid, (
            f"Invariant 4 VIOLATED: {agent_type.value} predictions contain non-binary values "
            f"under stressed context: {invalid[:5]}. "
            f"Amplification must operate on probabilities, not labels."
        )


class TestProbabilityRange:
    """Invariant 4b: probabilities must be in [0.0, 1.0]."""

    @pytest.mark.parametrize("agent_type", CLASSIFIER_AGENTS)
    def test_probabilities_in_range_healthy(self, engineered_df, engine, agent_type):
        result = engine.predict(engineered_df, agent_type, graph_context=CTX_HEALTHY)
        assert result.probabilities is not None, (
            f"{agent_type.value}: probabilities is None (model has no predict_proba?)"
        )
        out_of_range = [p for p in result.probabilities if not (0.0 <= p <= 1.0)]
        assert not out_of_range, (
            f"Invariant 4 VIOLATED: {agent_type.value} probabilities out of [0,1]: "
            f"{out_of_range[:5]}"
        )

    @pytest.mark.parametrize("agent_type", CLASSIFIER_AGENTS)
    def test_probabilities_in_range_stressed(self, engineered_df, engine, agent_type):
        result = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)
        assert result.probabilities is not None
        out_of_range = [p for p in result.probabilities if not (0.0 <= p <= 1.0)]
        assert not out_of_range, (
            f"Invariant 4 VIOLATED: {agent_type.value} probabilities out of [0,1] "
            f"after amplification: {out_of_range[:5]}. "
            f"np.clip(proba, 0, 1) must be applied after amplification."
        )


class TestRiskLevelConsistency:
    """Invariant 4c: risk_levels must be consistent with probabilities."""

    @pytest.mark.parametrize("agent_type", CLASSIFIER_AGENTS)
    def test_risk_levels_valid(self, engineered_df, engine, agent_type):
        result = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)
        invalid = [r for r in result.risk_levels if r not in VALID_RISK_LEVELS]
        assert not invalid, (
            f"{agent_type.value}: invalid risk_levels: {set(invalid)}"
        )

    @pytest.mark.parametrize("agent_type", CLASSIFIER_AGENTS)
    def test_risk_levels_match_probabilities(self, engineered_df, engine, agent_type):
        """High probability must map to high/critical risk level."""
        result = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)
        if result.probabilities is None:
            pytest.skip("No probabilities available")

        for prob, risk in zip(result.probabilities, result.risk_levels):
            if prob >= 0.75:
                assert risk == "critical", (
                    f"{agent_type.value}: prob={prob:.3f} but risk_level='{risk}' "
                    f"(expected 'critical' for prob >= 0.75)"
                )
            elif prob >= 0.50:
                assert risk == "high", (
                    f"{agent_type.value}: prob={prob:.3f} but risk_level='{risk}' "
                    f"(expected 'high' for 0.50 <= prob < 0.75)"
                )


class TestAmplificationEffect:
    """Invariant 4d: stressed context must produce higher mean probability."""

    @pytest.mark.parametrize("agent_type", CLASSIFIER_AGENTS)
    def test_stressed_probability_higher(self, engineered_df, engine, agent_type):
        res_h = engine.predict(engineered_df, agent_type, graph_context=CTX_HEALTHY)
        res_s = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)

        mean_h = float(np.mean(res_h.probabilities or [0.5]))
        mean_s = float(np.mean(res_s.probabilities or [0.5]))

        assert mean_s >= mean_h - 0.01, (
            f"{agent_type.value}: stressed mean_prob={mean_s:.4f} < "
            f"healthy mean_prob={mean_h:.4f}. "
            f"Amplification is not working or is inverted."
        )


class TestRegressorNotClipped:
    """Demand regressor predictions must NOT be clipped to {0,1}."""

    def test_demand_predictions_not_binary(self, engineered_df, engine):
        result = engine.predict(
            engineered_df, IntelligenceType.DEMAND, graph_context=CTX_HEALTHY
        )
        # Demand predictions are quantities — they should span a range > 1
        pred_range = max(result.predictions) - min(result.predictions)
        assert pred_range > 1.0, (
            f"Demand predictions look binary (range={pred_range:.4f}). "
            f"Regressor output must not be clipped to {{0,1}}."
        )

    def test_demand_predictions_finite(self, engineered_df, engine):
        result = engine.predict(
            engineered_df, IntelligenceType.DEMAND, graph_context=CTX_STRESSED
        )
        non_finite = [p for p in result.predictions if not np.isfinite(p)]
        assert not non_finite, (
            f"Demand predictions contain non-finite values: {non_finite[:5]}"
        )

    def test_demand_has_no_probabilities(self, engineered_df, engine):
        """Demand is a regressor — probabilities should be None."""
        result = engine.predict(
            engineered_df, IntelligenceType.DEMAND, graph_context=CTX_HEALTHY
        )
        assert result.probabilities is None, (
            f"Demand agent returned probabilities={result.probabilities[:3]}. "
            f"Regressors do not produce probabilities."
        )


class TestAmplificationMetadata:
    """graph_amplification metadata must be present and accurate."""

    def test_amplification_flag_set_for_stressed(self, engineered_df, engine):
        """At least one classifier agent must report amplified=True under stressed context."""
        any_amplified = False
        for agent_type in CLASSIFIER_AGENTS:
            result = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)
            if result.graph_amplification.get("amplified"):
                any_amplified = True
                break
        assert any_amplified, (
            "No classifier agent reported amplified=True under stressed context. "
            "Check _apply_graph_amplification logic."
        )

    def test_amplification_factor_positive(self, engineered_df, engine):
        for agent_type in CLASSIFIER_AGENTS:
            result = engine.predict(engineered_df, agent_type, graph_context=CTX_STRESSED)
            factor = result.graph_amplification.get("factor", 1.0)
            assert factor >= 1.0, (
                f"{agent_type.value}: amplification factor={factor} < 1.0. "
                f"Amplification must increase risk, not decrease it."
            )

"""
Unit tests for ML Prediction module.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.prediction import PredictionEngine, _classify_risk
from app.ml.registry import ModelRegistry
from app.ml.training import BaseTrainer
from app.ml.utils import IntelligenceType


def _make_sample_df(n_rows: int = 600) -> pd.DataFrame:
    """Create a sample dataframe."""
    np.random.seed(42)
    return pd.DataFrame({
        "order date (DateOrders)": pd.date_range("2020-01-01", periods=n_rows, freq="D"),
        "order_month": np.tile(range(1, 13), n_rows // 12 + 1)[:n_rows],
        "order_day_of_week": np.random.randint(0, 7, n_rows),
        "order_week_of_year": np.random.randint(1, 53, n_rows),
        "order_quarter": np.tile([1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4], n_rows // 12 + 1)[:n_rows],
        "order_is_weekend": np.random.randint(0, 2, n_rows),
        "Order Item Quantity": np.random.randint(1, 20, n_rows),
        "Sales": np.random.uniform(10, 1000, n_rows),
        "Order Profit Per Order": np.random.uniform(-50, 200, n_rows),
        "Product Price": np.random.uniform(5, 500, n_rows),
        "Order Item Discount": np.random.uniform(0, 0.5, n_rows),
        "Days for shipping (real)": np.random.randint(1, 10, n_rows),
        "Days for shipment (scheduled)": np.random.randint(1, 7, n_rows),
        "delivery_duration_days": np.random.randint(1, 15, n_rows),
        "Late_delivery_risk": np.random.randint(0, 2, n_rows),
    })


@pytest.fixture
def trained_registry():
    """Create a registry with a trained model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ModelRegistry(base_dir=Path(tmpdir))
        trainer = BaseTrainer(registry)
        df = _make_sample_df(600)
        trainer.train(df, IntelligenceType.INVENTORY, run_walk_forward=False)
        trainer.train(df, IntelligenceType.DEMAND, run_walk_forward=False)
        yield registry


class TestClassifyRisk:
    """Tests for risk classification."""

    def test_critical(self):
        assert _classify_risk(0.80) == "critical"

    def test_high(self):
        assert _classify_risk(0.60) == "high"

    def test_medium(self):
        assert _classify_risk(0.30) == "medium"

    def test_low(self):
        assert _classify_risk(0.10) == "low"


class TestPredictionEngine:
    """Tests for prediction engine."""

    def test_predict_classification(self, trained_registry):
        engine = PredictionEngine(trained_registry)
        df = _make_sample_df(50)
        result = engine.predict(df, IntelligenceType.INVENTORY)

        assert result.intelligence_type == "inventory"
        assert result.n_predictions == 50
        assert len(result.predictions) == 50
        assert result.probabilities is not None
        assert len(result.confidence_scores) == 50
        assert len(result.risk_levels) == 50
        assert result.prediction_time_ms > 0

    def test_predict_regression(self, trained_registry):
        engine = PredictionEngine(trained_registry)
        df = _make_sample_df(50)
        result = engine.predict(df, IntelligenceType.DEMAND)

        assert result.intelligence_type == "demand"
        assert result.n_predictions == 50
        assert result.probabilities is None  # Regression has no probabilities
        assert len(result.confidence_scores) == 50

    def test_predict_single(self, trained_registry):
        engine = PredictionEngine(trained_registry)
        record = {
            "order_month": 6,
            "order_day_of_week": 3,
            "order_week_of_year": 24,
            "order_quarter": 2,
            "order_is_weekend": 0,
            "Order Item Quantity": 5,
            "Sales": 150.0,
            "Order Profit Per Order": 30.0,
            "Product Price": 50.0,
            "Order Item Discount": 0.1,
            "Days for shipping (real)": 4,
            "Days for shipment (scheduled)": 3,
            "delivery_duration_days": 5,
        }
        pred = engine.predict_single(record, IntelligenceType.INVENTORY)

        assert pred.prediction in [0, 1]
        assert pred.probability is not None
        assert 0 <= pred.confidence <= 1.0
        assert pred.risk_level in ["low", "medium", "high", "critical"]

    def test_predict_no_model_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(base_dir=Path(tmpdir))
            engine = PredictionEngine(registry)
            df = _make_sample_df(10)

            with pytest.raises(FileNotFoundError):
                engine.predict(df, IntelligenceType.LOGISTICS)

    def test_to_dict(self, trained_registry):
        engine = PredictionEngine(trained_registry)
        df = _make_sample_df(20)
        result = engine.predict(df, IntelligenceType.INVENTORY)
        d = result.to_dict()

        assert "intelligence_type" in d
        assert "predictions_summary" in d
        assert "risk_distribution" in d

"""
Unit tests for Forecasting module.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.forecasting import ForecastEngine
from app.ml.registry import ModelRegistry
from app.ml.training import BaseTrainer
from app.ml.utils import IntelligenceType


def _make_sample_df(n_rows: int = 600) -> pd.DataFrame:
    """Create a sample dataframe with period columns."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="D")
    df = pd.DataFrame({
        "order date (DateOrders)": dates,
        "order_month": dates.month,
        "order_day_of_week": dates.dayofweek,
        "order_week_of_year": dates.isocalendar().week.astype(int),
        "order_quarter": dates.quarter,
        "order_is_weekend": (dates.dayofweek >= 5).astype(int),
        "Order Item Quantity": np.random.randint(1, 20, n_rows),
        "Sales": np.random.uniform(10, 1000, n_rows),
        "Order Profit Per Order": np.random.uniform(-50, 200, n_rows),
        "Product Price": np.random.uniform(5, 500, n_rows),
        "Order Item Discount": np.random.uniform(0, 0.5, n_rows),
        "Days for shipping (real)": np.random.randint(1, 10, n_rows),
        "Days for shipment (scheduled)": np.random.randint(1, 7, n_rows),
        "delivery_duration_days": np.random.randint(1, 15, n_rows),
        "Late_delivery_risk": np.random.randint(0, 2, n_rows),
        "period_monthly": dates.to_period("M").astype(str),
    })
    return df


@pytest.fixture
def trained_registry():
    """Create a registry with trained models."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ModelRegistry(base_dir=Path(tmpdir))
        trainer = BaseTrainer(registry)
        df = _make_sample_df(600)
        trainer.train(df, IntelligenceType.INVENTORY, run_walk_forward=False)
        trainer.train(df, IntelligenceType.DEMAND, run_walk_forward=False)
        yield registry


class TestForecastEngine:
    """Tests for forecast engine."""

    def test_forecast_classification(self, trained_registry):
        engine = ForecastEngine(trained_registry)
        df = _make_sample_df(600)
        result = engine.forecast_monthly(df, IntelligenceType.INVENTORY, horizon_months=3)

        assert result.intelligence_type == "inventory"
        assert result.forecast_horizon == 3
        assert len(result.forecast_periods) == 3
        assert result.generation_time_ms > 0
        assert result.generated_at != ""

    def test_forecast_regression(self, trained_registry):
        engine = ForecastEngine(trained_registry)
        df = _make_sample_df(600)
        result = engine.forecast_monthly(df, IntelligenceType.DEMAND, horizon_months=2)

        assert result.intelligence_type == "demand"
        assert len(result.forecast_periods) == 2

    def test_historical_backtest(self, trained_registry):
        engine = ForecastEngine(trained_registry)
        df = _make_sample_df(600)
        result = engine.forecast_monthly(df, IntelligenceType.INVENTORY, horizon_months=1)

        assert len(result.historical_periods) > 0

    def test_confidence_decay(self, trained_registry):
        engine = ForecastEngine(trained_registry)
        df = _make_sample_df(600)
        result = engine.forecast_monthly(df, IntelligenceType.INVENTORY, horizon_months=6)

        # Confidence should generally decrease with horizon
        if len(result.forecast_periods) >= 2:
            first_conf = result.forecast_periods[0].confidence_score
            last_conf = result.forecast_periods[-1].confidence_score
            # Due to decay factor, later periods should have lower confidence
            assert last_conf <= first_conf + 0.1  # Allow small tolerance

    def test_forecast_bounds(self, trained_registry):
        engine = ForecastEngine(trained_registry)
        df = _make_sample_df(600)
        result = engine.forecast_monthly(df, IntelligenceType.DEMAND, horizon_months=3)

        for fp in result.forecast_periods:
            assert fp.lower_bound <= fp.predicted_value
            assert fp.upper_bound >= fp.predicted_value

    def test_to_dict(self, trained_registry):
        engine = ForecastEngine(trained_registry)
        df = _make_sample_df(600)
        result = engine.forecast_monthly(df, IntelligenceType.INVENTORY, horizon_months=2)
        d = result.to_dict()

        assert "intelligence_type" in d
        assert "forecast_periods" in d
        assert "historical_periods" in d
        assert "mean_confidence" in d

    def test_no_model_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(base_dir=Path(tmpdir))
            engine = ForecastEngine(registry)
            df = _make_sample_df(100)

            with pytest.raises(FileNotFoundError):
                engine.forecast_monthly(df, IntelligenceType.LOGISTICS)

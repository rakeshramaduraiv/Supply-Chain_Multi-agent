"""
Integration tests for ML Pipeline (end-to-end).
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.forecasting import ForecastEngine
from app.ml.prediction import PredictionEngine
from app.ml.registry import ModelRegistry
from app.ml.training import TrainingOrchestrator
from app.ml.utils import IntelligenceType


def _make_full_dataset(n_rows: int = 1000) -> pd.DataFrame:
    """Create a realistic dataset simulating processed DataCo data."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="D")
    return pd.DataFrame({
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


class TestFullPipeline:
    """End-to-end integration tests for the ML pipeline."""

    def test_train_predict_forecast_cycle(self):
        """Test complete: Train → Predict → Forecast lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(base_dir=Path(tmpdir))
            df = _make_full_dataset(1000)

            # 1. Train all models
            orchestrator = TrainingOrchestrator(registry)
            train_results = orchestrator.train_all(df, dataset_version="test_v1")

            assert len(train_results) == 4
            for key, result in train_results.items():
                assert result.version_id != ""
                assert result.n_training_samples > 0
                assert result.metrics != {}

            # 2. Predict with each model
            engine = PredictionEngine(registry)
            test_df = df.tail(100)

            for intel_type in IntelligenceType:
                pred_result = engine.predict(test_df, intel_type)
                assert pred_result.n_predictions == 100
                assert pred_result.mean_confidence > 0

            # 3. Forecast with each model
            forecast_engine = ForecastEngine(registry)
            for intel_type in IntelligenceType:
                forecast_result = forecast_engine.forecast_monthly(
                    df, intel_type, horizon_months=3
                )
                assert len(forecast_result.forecast_periods) == 3
                assert forecast_result.mean_confidence > 0

    def test_model_versioning_lifecycle(self):
        """Test model versioning: train v1 → train v2 → rollback to v1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(base_dir=Path(tmpdir))
            df = _make_full_dataset(600)
            orchestrator = TrainingOrchestrator(registry)

            # Train v1
            result_v1 = orchestrator.train_single(df, IntelligenceType.SUPPLIER)
            v1_id = result_v1.version_id

            # Train v2
            result_v2 = orchestrator.train_single(df, IntelligenceType.SUPPLIER)
            v2_id = result_v2.version_id

            # Latest should be v2
            latest = registry.get_latest_version(IntelligenceType.SUPPLIER)
            assert latest.version_id == v2_id

            # Rollback to v1
            registry.rollback(IntelligenceType.SUPPLIER, v1_id)
            latest = registry.get_latest_version(IntelligenceType.SUPPLIER)
            assert latest.version_id == v1_id

            # Predictions should work with rolled-back model
            engine = PredictionEngine(registry)
            result = engine.predict(df.tail(10), IntelligenceType.SUPPLIER)
            assert result.n_predictions == 10

    def test_walk_forward_validation_integration(self):
        """Test walk-forward validation produces consistent results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(base_dir=Path(tmpdir))
            df = _make_full_dataset(1000)

            from app.ml.training import BaseTrainer
            trainer = BaseTrainer(registry)
            result = trainer.train(
                df, IntelligenceType.INVENTORY, run_walk_forward=True
            )

            assert result.walk_forward_result is not None
            wf = result.walk_forward_result
            assert wf["n_folds"] >= 2
            assert "accuracy_mean" in wf["aggregated_metrics"]
            assert wf["total_duration_ms"] > 0

    def test_feature_importance_consistency(self):
        """Test feature importance is consistent with model features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(base_dir=Path(tmpdir))
            df = _make_full_dataset(600)

            from app.ml.training import BaseTrainer
            trainer = BaseTrainer(registry)
            result = trainer.train(
                df, IntelligenceType.LOGISTICS, run_walk_forward=False
            )

            fi = result.feature_importance
            assert len(fi["feature_names"]) == len(result.features_used)
            assert len(fi["gain_importance"]) == len(result.features_used)
            assert fi["top_features"][0]["rank"] == 1

    def test_confidence_scores_valid(self):
        """Test confidence scores are within valid range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(base_dir=Path(tmpdir))
            df = _make_full_dataset(600)

            orchestrator = TrainingOrchestrator(registry)
            orchestrator.train_single(df, IntelligenceType.INVENTORY)

            engine = PredictionEngine(registry)
            result = engine.predict(df.tail(50), IntelligenceType.INVENTORY)

            for score in result.confidence_scores:
                assert 0.0 <= score <= 1.0

            assert 0.0 <= result.mean_confidence <= 1.0

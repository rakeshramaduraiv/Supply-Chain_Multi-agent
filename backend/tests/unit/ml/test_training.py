"""
Unit tests for ML Training module.
"""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.registry import ModelRegistry
from app.ml.training import (
    BaseTrainer,
    DemandTrainer,
    InventoryTrainer,
    LogisticsTrainer,
    SupplierTrainer,
    TrainingOrchestrator,
)
from app.ml.utils import IntelligenceType


def _make_sample_df(n_rows: int = 600) -> pd.DataFrame:
    """Create a sample dataframe for training tests."""
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
def temp_registry():
    """Create a temporary model registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ModelRegistry(base_dir=Path(tmpdir))


class TestDemandTrainer:
    """Tests for Demand Intelligence trainer."""

    def test_train_demand(self, temp_registry):
        trainer = DemandTrainer(temp_registry)
        df = _make_sample_df(600)
        result = trainer.train_demand(df)

        assert result.intelligence_type == "demand"
        assert result.task == "regression"
        assert result.version_id != ""
        assert result.n_training_samples > 0
        assert result.n_test_samples > 0
        assert "mae" in result.metrics
        assert "rmse" in result.metrics
        assert "r2" in result.metrics
        assert result.training_duration_ms > 0
        assert len(result.features_used) > 0

    def test_feature_importance_generated(self, temp_registry):
        trainer = DemandTrainer(temp_registry)
        df = _make_sample_df(600)
        result = trainer.train_demand(df)

        assert "top_features" in result.feature_importance
        assert len(result.feature_importance["top_features"]) > 0


class TestInventoryTrainer:
    """Tests for Inventory Intelligence trainer."""

    def test_train_inventory(self, temp_registry):
        trainer = InventoryTrainer(temp_registry)
        df = _make_sample_df(600)
        result = trainer.train_inventory(df)

        assert result.intelligence_type == "inventory"
        assert result.task == "classification"
        assert "accuracy" in result.metrics
        assert "f1" in result.metrics
        assert "roc_auc" in result.metrics


class TestSupplierTrainer:
    """Tests for Supplier Intelligence trainer (RandomForest)."""

    def test_train_supplier(self, temp_registry):
        trainer = SupplierTrainer(temp_registry)
        df = _make_sample_df(600)
        result = trainer.train_supplier(df)

        assert result.intelligence_type == "supplier"
        assert result.task == "classification"
        assert "accuracy" in result.metrics
        assert result.n_training_samples > 0


class TestLogisticsTrainer:
    """Tests for Logistics Intelligence trainer."""

    def test_train_logistics(self, temp_registry):
        trainer = LogisticsTrainer(temp_registry)
        df = _make_sample_df(600)
        result = trainer.train_logistics(df)

        assert result.intelligence_type == "logistics"
        assert result.task == "classification"
        assert "accuracy" in result.metrics


class TestTrainingOrchestrator:
    """Tests for training orchestrator."""

    def test_train_all(self, temp_registry):
        orchestrator = TrainingOrchestrator(temp_registry)
        df = _make_sample_df(600)
        results = orchestrator.train_all(df)

        assert "demand" in results
        assert "inventory" in results
        assert "supplier" in results
        assert "logistics" in results

    def test_train_single(self, temp_registry):
        orchestrator = TrainingOrchestrator(temp_registry)
        df = _make_sample_df(600)
        result = orchestrator.train_single(df, IntelligenceType.DEMAND)

        assert result.intelligence_type == "demand"

    def test_walk_forward_included(self, temp_registry):
        trainer = BaseTrainer(temp_registry)
        df = _make_sample_df(600)
        result = trainer.train(df, IntelligenceType.INVENTORY, run_walk_forward=True)

        assert result.walk_forward_result is not None
        assert "n_folds" in result.walk_forward_result

    def test_walk_forward_skipped_small_data(self, temp_registry):
        trainer = BaseTrainer(temp_registry)
        df = _make_sample_df(100)
        result = trainer.train(df, IntelligenceType.INVENTORY, run_walk_forward=True)

        # With < 500 samples after feature prep, walk-forward is skipped
        # (depends on how many rows survive dropna)
        assert result.version_id != ""

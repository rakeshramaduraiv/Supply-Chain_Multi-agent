"""
Unit tests for ML Utilities module.
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.utils import (
    FEATURE_CONFIGS,
    FeatureConfig,
    IntelligenceType,
    ModelTask,
    chronological_split,
    prepare_features,
)


def _make_sample_df(n_rows: int = 100) -> pd.DataFrame:
    """Create a sample dataframe with required features."""
    np.random.seed(42)
    return pd.DataFrame({
        "order_month": np.random.randint(1, 13, n_rows),
        "order_day_of_week": np.random.randint(0, 7, n_rows),
        "order_week_of_year": np.random.randint(1, 53, n_rows),
        "order_quarter": np.random.randint(1, 5, n_rows),
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


class TestFeatureConfigs:
    """Tests for feature configuration definitions."""

    def test_all_intelligence_types_have_configs(self):
        for intel_type in IntelligenceType:
            assert intel_type in FEATURE_CONFIGS

    def test_demand_config(self):
        config = FEATURE_CONFIGS[IntelligenceType.DEMAND]
        assert config.task == ModelTask.REGRESSION
        assert config.target == "Order Item Quantity"
        assert len(config.features) > 0

    def test_inventory_config(self):
        config = FEATURE_CONFIGS[IntelligenceType.INVENTORY]
        assert config.task == ModelTask.CLASSIFICATION
        assert config.target == "Late_delivery_risk"

    def test_supplier_config(self):
        config = FEATURE_CONFIGS[IntelligenceType.SUPPLIER]
        assert config.task == ModelTask.CLASSIFICATION
        assert config.target == "Late_delivery_risk"

    def test_logistics_config(self):
        config = FEATURE_CONFIGS[IntelligenceType.LOGISTICS]
        assert config.task == ModelTask.CLASSIFICATION
        assert config.target == "Late_delivery_risk"


class TestPrepareFeatures:
    """Tests for feature preparation."""

    def test_basic_preparation(self):
        df = _make_sample_df(50)
        config = FEATURE_CONFIGS[IntelligenceType.DEMAND]
        X, y = prepare_features(df, config)

        assert len(X) == len(y)
        assert len(X) > 0
        assert all(col in X.columns for col in config.features if col in df.columns)

    def test_drops_null_rows(self):
        df = _make_sample_df(50)
        df.loc[0:4, "Sales"] = np.nan
        config = FEATURE_CONFIGS[IntelligenceType.DEMAND]
        X, y = prepare_features(df, config)

        assert len(X) == 45

    def test_missing_target_raises(self):
        df = _make_sample_df(50)
        config = FeatureConfig(
            features=["Sales"],
            target="nonexistent_column",
            task=ModelTask.REGRESSION,
        )
        with pytest.raises(ValueError, match="Target column"):
            prepare_features(df, config)

    def test_no_features_raises(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        config = FeatureConfig(
            features=["nonexistent"],
            target="a",
            task=ModelTask.REGRESSION,
        )
        with pytest.raises(ValueError, match="No configured features"):
            prepare_features(df, config)


class TestChronologicalSplit:
    """Tests for chronological splitting."""

    def test_default_split(self):
        df = _make_sample_df(100)
        train, test = chronological_split(df, train_ratio=0.8)

        assert len(train) == 80
        assert len(test) == 20

    def test_custom_ratio(self):
        df = _make_sample_df(100)
        train, test = chronological_split(df, train_ratio=0.7)

        assert len(train) == 70
        assert len(test) == 30

    def test_preserves_order(self):
        df = _make_sample_df(100)
        df["idx"] = range(100)
        train, test = chronological_split(df, train_ratio=0.8)

        assert train["idx"].iloc[-1] < test["idx"].iloc[0]

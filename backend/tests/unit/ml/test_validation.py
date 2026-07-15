"""
Unit tests for Walk-Forward Validation module.
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.utils import FEATURE_CONFIGS, IntelligenceType, ModelTask
from app.ml.validation import WalkForwardValidator


def _make_sample_df(n_rows: int = 500) -> pd.DataFrame:
    """Create a sample dataframe for validation testing."""
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


class TestWalkForwardValidator:
    """Tests for walk-forward validation."""

    def test_generate_splits(self):
        validator = WalkForwardValidator(n_splits=5)
        splits = validator.generate_splits(n_samples=1000)

        assert len(splits) == 5
        for (train_start, train_end), (test_start, test_end) in splits:
            assert train_start == 0
            assert train_end == test_start
            assert test_end > test_start

    def test_splits_no_overlap(self):
        validator = WalkForwardValidator(n_splits=3)
        splits = validator.generate_splits(n_samples=500)

        for (_, train_end), (test_start, _) in splits:
            assert train_end == test_start  # No gap, no overlap

    def test_expanding_window(self):
        validator = WalkForwardValidator(n_splits=4)
        splits = validator.generate_splits(n_samples=800)

        train_sizes = [train_end - train_start for (train_start, train_end), _ in splits]
        # Training window should expand
        for i in range(1, len(train_sizes)):
            assert train_sizes[i] >= train_sizes[i - 1]

    def test_validate_classification(self):
        from lightgbm import LGBMClassifier

        df = _make_sample_df(500)
        feature_config = FEATURE_CONFIGS[IntelligenceType.INVENTORY]
        validator = WalkForwardValidator(n_splits=3)

        result = validator.validate(
            df=df,
            feature_config=feature_config,
            model_factory=lambda: LGBMClassifier(
                n_estimators=10, max_depth=3, verbose=-1, random_state=42
            ),
        )

        assert result.n_folds == 3
        assert len(result.folds) == 3
        assert result.total_duration_ms > 0
        assert "accuracy_mean" in result.aggregated_metrics

    def test_validate_regression(self):
        from lightgbm import LGBMRegressor

        df = _make_sample_df(500)
        feature_config = FEATURE_CONFIGS[IntelligenceType.DEMAND]
        validator = WalkForwardValidator(n_splits=3)

        result = validator.validate(
            df=df,
            feature_config=feature_config,
            model_factory=lambda: LGBMRegressor(
                n_estimators=10, max_depth=3, verbose=-1, random_state=42
            ),
        )

        assert result.n_folds == 3
        assert len(result.folds) == 3
        assert "mae_mean" in result.aggregated_metrics
        assert "r2_mean" in result.aggregated_metrics

    def test_to_dict(self):
        from lightgbm import LGBMClassifier

        df = _make_sample_df(500)
        feature_config = FEATURE_CONFIGS[IntelligenceType.LOGISTICS]
        validator = WalkForwardValidator(n_splits=2)

        result = validator.validate(
            df=df,
            feature_config=feature_config,
            model_factory=lambda: LGBMClassifier(
                n_estimators=10, max_depth=3, verbose=-1, random_state=42
            ),
        )

        d = result.to_dict()
        assert "n_folds" in d
        assert "aggregated_metrics" in d
        assert "folds" in d
        assert len(d["folds"]) == 2

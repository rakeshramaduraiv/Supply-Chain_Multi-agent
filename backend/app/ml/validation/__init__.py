"""
AMASCI Walk-Forward Validation
================================
Enterprise walk-forward (expanding window) validation for time-series ML.

Strategy:
    Historical Window → Train → Predict Next Period → Evaluate → Expand → Repeat
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.ml.metrics import (
    ClassificationMetrics,
    RegressionMetrics,
    compute_classification_metrics,
    compute_regression_metrics,
)
from app.ml.utils import FeatureConfig, ModelTask, prepare_features

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardFold:
    """Result of a single walk-forward fold."""
    fold_index: int
    train_size: int
    test_size: int
    train_start_idx: int
    train_end_idx: int
    test_start_idx: int
    test_end_idx: int
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class WalkForwardResult:
    """Complete walk-forward validation result."""
    n_folds: int
    folds: list[WalkForwardFold] = field(default_factory=list)
    aggregated_metrics: dict[str, Any] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    best_fold_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_folds": self.n_folds,
            "aggregated_metrics": self.aggregated_metrics,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "best_fold_index": self.best_fold_index,
            "folds": [
                {
                    "fold_index": f.fold_index,
                    "train_size": f.train_size,
                    "test_size": f.test_size,
                    "metrics": f.metrics,
                    "duration_ms": round(f.duration_ms, 2),
                }
                for f in self.folds
            ],
        }


class WalkForwardValidator:
    """
    Walk-forward (expanding window) cross-validation.

    Splits data chronologically into expanding training windows
    with fixed-size test windows. No data leakage.
    """

    def __init__(
        self,
        n_splits: int = 5,
        min_train_ratio: float = 0.5,
        test_ratio: float = 0.1,
    ):
        self.n_splits = n_splits
        self.min_train_ratio = min_train_ratio
        self.test_ratio = test_ratio

    def generate_splits(
        self, n_samples: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """
        Generate train/test index ranges for walk-forward splits.

        Returns list of ((train_start, train_end), (test_start, test_end)).
        """
        min_train_size = int(n_samples * self.min_train_ratio)
        test_size = max(int(n_samples * self.test_ratio), 1)
        remaining = n_samples - min_train_size
        step = max(remaining // self.n_splits, 1)

        splits = []
        for i in range(self.n_splits):
            train_end = min_train_size + i * step
            test_start = train_end
            test_end = min(test_start + test_size, n_samples)

            if test_start >= n_samples or test_end <= test_start:
                break

            splits.append(((0, train_end), (test_start, test_end)))

        return splits

    def validate(
        self,
        df: pd.DataFrame,
        feature_config: FeatureConfig,
        model_factory: Any,
    ) -> WalkForwardResult:
        """
        Execute walk-forward validation.

        Args:
            df: Chronologically sorted dataframe
            feature_config: Feature configuration
            model_factory: Callable that returns a fresh model instance
        """
        start_time = time.perf_counter()

        X, y = prepare_features(df, feature_config)
        n_samples = len(X)
        splits = self.generate_splits(n_samples)

        result = WalkForwardResult(n_folds=len(splits))
        fold_metrics_list: list[dict[str, float]] = []

        for fold_idx, ((train_start, train_end), (test_start, test_end)) in enumerate(splits):
            fold_start = time.perf_counter()

            X_train = X.iloc[train_start:train_end]
            y_train = y.iloc[train_start:train_end]
            X_test = X.iloc[test_start:test_end]
            y_test = y.iloc[test_start:test_end]

            # Train fresh model
            model = model_factory()
            model.fit(X_train, y_train)

            # Predict
            y_pred = model.predict(X_test)

            # Compute metrics
            if feature_config.task == ModelTask.CLASSIFICATION:
                y_prob = None
                if hasattr(model, "predict_proba"):
                    y_prob = model.predict_proba(X_test)[:, 1]
                metrics_obj = compute_classification_metrics(y_test.values, y_pred, y_prob)
                fold_metrics = metrics_obj.to_dict()
            else:
                metrics_obj = compute_regression_metrics(y_test.values, y_pred)
                fold_metrics = metrics_obj.to_dict()

            fold_duration = (time.perf_counter() - fold_start) * 1000

            fold = WalkForwardFold(
                fold_index=fold_idx,
                train_size=len(X_train),
                test_size=len(X_test),
                train_start_idx=train_start,
                train_end_idx=train_end,
                test_start_idx=test_start,
                test_end_idx=test_end,
                metrics=fold_metrics,
                duration_ms=fold_duration,
            )
            result.folds.append(fold)
            fold_metrics_list.append(fold_metrics)

            logger.info(
                f"Fold {fold_idx}: train={len(X_train)}, test={len(X_test)}, "
                f"duration={fold_duration:.1f}ms"
            )

        # Aggregate metrics across folds
        if fold_metrics_list:
            result.aggregated_metrics = self._aggregate_metrics(fold_metrics_list)
            result.best_fold_index = self._find_best_fold(
                fold_metrics_list, feature_config.task
            )

        result.total_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Walk-forward validation complete: {len(splits)} folds, "
            f"{result.total_duration_ms:.1f}ms total"
        )
        return result

    def _aggregate_metrics(self, metrics_list: list[dict[str, float]]) -> dict[str, Any]:
        """Compute mean and std of metrics across folds."""
        aggregated: dict[str, Any] = {}
        numeric_keys = [
            k for k in metrics_list[0]
            if isinstance(metrics_list[0][k], (int, float))
        ]

        for key in numeric_keys:
            values = [m[key] for m in metrics_list if key in m]
            if values:
                aggregated[f"{key}_mean"] = round(float(np.mean(values)), 6)
                aggregated[f"{key}_std"] = round(float(np.std(values)), 6)

        return aggregated

    def _find_best_fold(
        self, metrics_list: list[dict[str, float]], task: ModelTask
    ) -> int:
        """Find the best fold based on primary metric."""
        if task == ModelTask.CLASSIFICATION:
            primary_key = "f1"
        else:
            primary_key = "r2"

        values = [m.get(primary_key, 0.0) for m in metrics_list]
        return int(np.argmax(values))

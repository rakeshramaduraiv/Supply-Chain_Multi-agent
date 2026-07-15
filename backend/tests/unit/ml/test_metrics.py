"""
Unit tests for ML Metrics module.
"""

import numpy as np
import pytest

from app.ml.metrics import (
    ClassificationMetrics,
    RegressionMetrics,
    compute_classification_metrics,
    compute_regression_metrics,
)


class TestRegressionMetrics:
    """Tests for regression metrics computation."""

    def test_perfect_predictions(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        metrics = compute_regression_metrics(y_true, y_pred)

        assert metrics.mae == 0.0
        assert metrics.rmse == 0.0
        assert metrics.r2 == 1.0
        assert metrics.n_samples == 5

    def test_imperfect_predictions(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.1, 2.2, 2.8, 4.1, 5.3])
        metrics = compute_regression_metrics(y_true, y_pred)

        assert metrics.mae > 0
        assert metrics.rmse > 0
        assert 0 < metrics.r2 < 1.0
        assert metrics.n_samples == 5

    def test_mape_with_zeros(self):
        y_true = np.array([0.0, 0.0, 3.0, 4.0])
        y_pred = np.array([0.1, 0.2, 3.1, 4.2])
        metrics = compute_regression_metrics(y_true, y_pred)

        # MAPE should only consider non-zero actuals
        assert metrics.mape > 0

    def test_to_dict(self):
        metrics = RegressionMetrics(mae=1.5, rmse=2.0, mape=10.0, r2=0.85, n_samples=100)
        d = metrics.to_dict()
        assert "mae" in d
        assert "rmse" in d
        assert "mape" in d
        assert "r2" in d
        assert d["n_samples"] == 100


class TestClassificationMetrics:
    """Tests for classification metrics computation."""

    def test_perfect_predictions(self):
        y_true = np.array([0, 1, 0, 1, 1])
        y_pred = np.array([0, 1, 0, 1, 1])
        y_prob = np.array([0.1, 0.9, 0.2, 0.8, 0.95])
        metrics = compute_classification_metrics(y_true, y_pred, y_prob)

        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1 == 1.0
        assert metrics.roc_auc == 1.0
        assert metrics.n_samples == 5

    def test_imperfect_predictions(self):
        y_true = np.array([0, 1, 0, 1, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 1, 1, 0, 0, 1, 0])
        y_prob = np.array([0.2, 0.8, 0.6, 0.7, 0.4, 0.3, 0.9, 0.1])
        metrics = compute_classification_metrics(y_true, y_pred, y_prob)

        assert 0 < metrics.accuracy < 1.0
        assert 0 < metrics.f1 < 1.0
        assert metrics.n_samples == 8

    def test_without_probabilities(self):
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 1, 1])
        metrics = compute_classification_metrics(y_true, y_pred)

        assert metrics.roc_auc == 0.0  # No probabilities provided
        assert metrics.accuracy > 0

    def test_confusion_matrix_shape(self):
        y_true = np.array([0, 1, 0, 1, 0, 1])
        y_pred = np.array([0, 1, 1, 0, 0, 1])
        metrics = compute_classification_metrics(y_true, y_pred)

        assert len(metrics.confusion_matrix) == 2
        assert len(metrics.confusion_matrix[0]) == 2

    def test_to_dict(self):
        metrics = ClassificationMetrics(
            accuracy=0.9, precision=0.85, recall=0.88,
            f1=0.86, roc_auc=0.92, confusion_matrix=[[10, 2], [1, 12]],
            n_samples=25,
        )
        d = metrics.to_dict()
        assert d["accuracy"] == 0.9
        assert d["n_samples"] == 25

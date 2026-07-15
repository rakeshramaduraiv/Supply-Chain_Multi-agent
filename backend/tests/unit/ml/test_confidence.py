"""
Unit tests for Confidence Engine module.
"""

import numpy as np
import pytest

from app.ml.confidence import (
    ConfidenceResult,
    compute_classification_confidence,
    compute_regression_confidence,
)


class TestClassificationConfidence:
    """Tests for classification confidence estimation."""

    def test_high_confidence_predictions(self):
        y_prob = np.array([0.95, 0.02, 0.98, 0.01, 0.99])
        result = compute_classification_confidence(y_prob)

        assert result.mean_confidence > 0.8
        assert all(c > 0.8 for c in result.confidence_scores)

    def test_low_confidence_predictions(self):
        y_prob = np.array([0.48, 0.52, 0.49, 0.51, 0.50])
        result = compute_classification_confidence(y_prob)

        assert result.mean_confidence < 0.2

    def test_confidence_range(self):
        y_prob = np.random.rand(100)
        result = compute_classification_confidence(y_prob)

        assert all(0 <= c <= 1.0 for c in result.confidence_scores)

    def test_uncertainty_complement(self):
        y_prob = np.array([0.9, 0.1, 0.7, 0.3])
        result = compute_classification_confidence(y_prob)

        for conf, unc in zip(result.confidence_scores, result.uncertainty):
            assert abs(conf + unc - 1.0) < 1e-10

    def test_calibration_error_with_labels(self):
        y_prob = np.array([0.9, 0.8, 0.7, 0.2, 0.1])
        y_true = np.array([1, 1, 1, 0, 0])
        result = compute_classification_confidence(y_prob, y_true)

        assert result.calibration_error >= 0

    def test_to_dict(self):
        y_prob = np.array([0.9, 0.1, 0.6, 0.4])
        result = compute_classification_confidence(y_prob)
        d = result.to_dict()

        assert "mean_confidence" in d
        assert "calibration_error" in d
        assert "n_predictions" in d
        assert "confidence_distribution" in d
        assert "high" in d["confidence_distribution"]


class TestRegressionConfidence:
    """Tests for regression confidence estimation."""

    def test_with_true_values(self):
        y_pred = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        y_true = np.array([10.5, 19.5, 30.2, 39.8, 50.1])
        result = compute_regression_confidence(y_pred, y_true)

        assert result.mean_confidence > 0.0
        assert all(0 <= c <= 1.0 for c in result.confidence_scores)

    def test_without_true_values(self):
        y_pred = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        result = compute_regression_confidence(y_pred)

        assert len(result.confidence_scores) == 5
        assert all(0 <= c <= 1.0 for c in result.confidence_scores)

    def test_perfect_predictions(self):
        y_pred = np.array([1.0, 2.0, 3.0])
        y_true = np.array([1.0, 2.0, 3.0])
        result = compute_regression_confidence(y_pred, y_true)

        assert result.mean_confidence == 1.0

    def test_uncertainty_complement(self):
        y_pred = np.random.rand(50) * 100
        y_true = y_pred + np.random.randn(50) * 5
        result = compute_regression_confidence(y_pred, y_true)

        for conf, unc in zip(result.confidence_scores, result.uncertainty):
            assert abs(conf + unc - 1.0) < 1e-10

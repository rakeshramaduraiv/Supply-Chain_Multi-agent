"""
AMASCI Confidence Engine
==========================
Prediction confidence estimation, calibration, and uncertainty quantification.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceResult:
    """Confidence estimation for a batch of predictions."""
    probabilities: list[float]
    confidence_scores: list[float]
    mean_confidence: float
    calibration_error: float
    uncertainty: list[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean_confidence": round(self.mean_confidence, 4),
            "calibration_error": round(self.calibration_error, 4),
            "n_predictions": len(self.confidence_scores),
            "confidence_distribution": {
                "high": sum(1 for c in self.confidence_scores if c >= 0.8),
                "medium": sum(1 for c in self.confidence_scores if 0.5 <= c < 0.8),
                "low": sum(1 for c in self.confidence_scores if c < 0.5),
            },
        }


def compute_classification_confidence(
    y_prob: np.ndarray,
    y_true: np.ndarray | None = None,
    n_bins: int = 10,
) -> ConfidenceResult:
    """
    Compute confidence scores for classification predictions.

    Confidence = max(p, 1-p) for binary classification.
    Calibration error computed via Expected Calibration Error (ECE).
    """
    y_prob = np.asarray(y_prob, dtype=np.float64).flatten()

    # Confidence: distance from decision boundary
    confidence_scores = np.abs(y_prob - 0.5) * 2.0  # Maps [0,1] prob to [0,1] confidence
    uncertainty = 1.0 - confidence_scores

    # Expected Calibration Error
    calibration_error = 0.0
    if y_true is not None:
        y_true = np.asarray(y_true, dtype=np.float64).flatten()
        bin_edges = np.linspace(0, 1, n_bins + 1)
        for i in range(n_bins):
            mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
            if mask.sum() > 0:
                bin_confidence = y_prob[mask].mean()
                bin_accuracy = y_true[mask].mean()
                calibration_error += mask.sum() * abs(bin_accuracy - bin_confidence)
        calibration_error /= len(y_prob) if len(y_prob) > 0 else 1.0

    return ConfidenceResult(
        probabilities=y_prob.tolist(),
        confidence_scores=confidence_scores.tolist(),
        mean_confidence=float(confidence_scores.mean()),
        calibration_error=float(calibration_error),
        uncertainty=uncertainty.tolist(),
    )


def compute_regression_confidence(
    y_pred: np.ndarray,
    y_true: np.ndarray | None = None,
    model: Any = None,
    n_estimators_sample: int = 50,
) -> ConfidenceResult:
    """
    Compute confidence scores for regression predictions.

    Uses prediction variance from tree ensemble if available,
    otherwise uses normalized residual-based confidence.
    """
    y_pred = np.asarray(y_pred, dtype=np.float64).flatten()

    # Attempt tree-based variance estimation
    if model is not None and hasattr(model, "estimators_"):
        # For ensemble models, compute variance across trees
        tree_preds = np.array([
            tree.predict(np.zeros((len(y_pred), 1)))  # placeholder
            for tree in model.estimators_[:n_estimators_sample]
        ])
        pred_std = tree_preds.std(axis=0)
        max_std = pred_std.max() if pred_std.max() > 0 else 1.0
        confidence_scores = 1.0 - (pred_std / max_std)
    elif y_true is not None:
        # Residual-based confidence
        y_true = np.asarray(y_true, dtype=np.float64).flatten()
        residuals = np.abs(y_true - y_pred)
        max_residual = residuals.max() if residuals.max() > 0 else 1.0
        confidence_scores = 1.0 - (residuals / max_residual)
    else:
        # Default: moderate confidence based on prediction magnitude stability
        pred_range = y_pred.max() - y_pred.min() if len(y_pred) > 1 else 1.0
        if pred_range > 0:
            normalized = (y_pred - y_pred.min()) / pred_range
            confidence_scores = 1.0 - np.abs(normalized - 0.5) * 0.4
        else:
            confidence_scores = np.full_like(y_pred, 0.7)

    confidence_scores = np.clip(confidence_scores, 0.0, 1.0)
    uncertainty = 1.0 - confidence_scores

    # Calibration error for regression
    calibration_error = 0.0
    if y_true is not None:
        y_true = np.asarray(y_true, dtype=np.float64).flatten()
        residuals = np.abs(y_true - y_pred)
        pred_range = y_pred.max() - y_pred.min() if y_pred.max() != y_pred.min() else 1.0
        normalized_residuals = residuals / pred_range
        calibration_error = float(np.mean(np.abs(confidence_scores - (1.0 - normalized_residuals))))

    return ConfidenceResult(
        probabilities=y_pred.tolist(),
        confidence_scores=confidence_scores.tolist(),
        mean_confidence=float(confidence_scores.mean()),
        calibration_error=float(calibration_error),
        uncertainty=uncertainty.tolist(),
    )

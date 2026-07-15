"""
AMASCI ML Metrics
==================
Comprehensive evaluation metrics for regression and classification tasks.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


@dataclass
class RegressionMetrics:
    """Regression evaluation metrics."""
    mae: float = 0.0
    rmse: float = 0.0
    mape: float = 0.0
    r2: float = 0.0
    n_samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mae": round(self.mae, 6),
            "rmse": round(self.rmse, 6),
            "mape": round(self.mape, 6),
            "r2": round(self.r2, 6),
            "n_samples": self.n_samples,
        }


@dataclass
class ClassificationMetrics:
    """Classification evaluation metrics."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    roc_auc: float = 0.0
    confusion_matrix: list[list[int]] = field(default_factory=list)
    n_samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "accuracy": round(self.accuracy, 6),
            "precision": round(self.precision, 6),
            "recall": round(self.recall, 6),
            "f1": round(self.f1, 6),
            "roc_auc": round(self.roc_auc, 6),
            "confusion_matrix": self.confusion_matrix,
            "n_samples": self.n_samples,
        }


def compute_regression_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> RegressionMetrics:
    """Compute all regression metrics."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))

    # MAPE with zero-safe denominator
    mask = y_true != 0
    if mask.sum() > 0:
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
    else:
        mape = 0.0

    metrics = RegressionMetrics(
        mae=mae,
        rmse=rmse,
        mape=mape,
        r2=r2,
        n_samples=len(y_true),
    )
    logger.info(f"Regression metrics: MAE={mae:.4f}, RMSE={rmse:.4f}, R²={r2:.4f}")
    return metrics


def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray | None = None,
) -> ClassificationMetrics:
    """Compute all classification metrics."""
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)

    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, average="binary", zero_division=0))
    rec = float(recall_score(y_true, y_pred, average="binary", zero_division=0))
    f1 = float(f1_score(y_true, y_pred, average="binary", zero_division=0))

    auc = 0.0
    if y_prob is not None:
        try:
            auc = float(roc_auc_score(y_true, y_prob))
        except ValueError:
            auc = 0.0

    cm = confusion_matrix(y_true, y_pred).tolist()

    metrics = ClassificationMetrics(
        accuracy=acc,
        precision=prec,
        recall=rec,
        f1=f1,
        roc_auc=auc,
        confusion_matrix=cm,
        n_samples=len(y_true),
    )
    logger.info(f"Classification metrics: Acc={acc:.4f}, F1={f1:.4f}, AUC={auc:.4f}")
    return metrics

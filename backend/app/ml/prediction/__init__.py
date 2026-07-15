"""
AMASCI Prediction Module
==========================
Real-time and batch prediction engines for all intelligence services.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.ml.confidence import (
    compute_classification_confidence,
    compute_regression_confidence,
)
from app.ml.registry import ModelRegistry
from app.ml.utils import FEATURE_CONFIGS, IntelligenceType, ModelTask

logger = logging.getLogger(__name__)


@dataclass
class PredictionRecord:
    """Single prediction result."""
    prediction: float
    probability: float | None = None
    confidence: float = 0.0
    risk_level: str = ""


@dataclass
class PredictionResult:
    """Batch prediction result."""
    intelligence_type: str
    model_version: str
    predictions: list[float]
    probabilities: list[float] | None = None
    confidence_scores: list[float] = field(default_factory=list)
    risk_levels: list[str] = field(default_factory=list)
    mean_confidence: float = 0.0
    n_predictions: int = 0
    prediction_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intelligence_type": self.intelligence_type,
            "model_version": self.model_version,
            "n_predictions": self.n_predictions,
            "mean_confidence": round(self.mean_confidence, 4),
            "prediction_time_ms": round(self.prediction_time_ms, 2),
            "predictions_summary": {
                "mean": round(float(np.mean(self.predictions)), 4) if self.predictions else 0,
                "std": round(float(np.std(self.predictions)), 4) if self.predictions else 0,
                "min": round(float(np.min(self.predictions)), 4) if self.predictions else 0,
                "max": round(float(np.max(self.predictions)), 4) if self.predictions else 0,
            },
            "risk_distribution": self._risk_distribution(),
            "metadata": self.metadata,
        }

    def _risk_distribution(self) -> dict[str, int]:
        if not self.risk_levels:
            return {}
        from collections import Counter
        return dict(Counter(self.risk_levels))


def _classify_risk(probability: float) -> str:
    """Classify risk level from probability."""
    if probability >= 0.75:
        return "critical"
    elif probability >= 0.50:
        return "high"
    elif probability >= 0.25:
        return "medium"
    return "low"


class PredictionEngine:
    """
    Unified prediction engine for all intelligence services.

    Loads model from registry, applies feature alignment,
    generates predictions with confidence scores.
    """

    def __init__(self, registry: ModelRegistry | None = None):
        self.registry = registry or ModelRegistry()

    def predict(
        self,
        df: pd.DataFrame,
        intelligence_type: IntelligenceType,
        version_id: str | None = None,
    ) -> PredictionResult:
        """
        Generate predictions for a dataframe.

        Args:
            df: Input dataframe with required features
            intelligence_type: Which intelligence model to use
            version_id: Specific model version (None = latest)
        """
        start_time = time.perf_counter()
        feature_config = FEATURE_CONFIGS[intelligence_type]

        # Load model
        model = self.registry.load_model(intelligence_type, version_id)
        version = self.registry.get_version(intelligence_type, version_id)
        model_version = version.version_id if version else "unknown"

        # Align features
        available_features = [f for f in feature_config.features if f in df.columns]
        if not available_features:
            raise ValueError(f"No features available for {intelligence_type.value}")

        X = df[available_features].copy()

        # Handle missing features by filling with 0
        for feat in feature_config.features:
            if feat not in X.columns:
                X[feat] = 0

        X = X[feature_config.features]
        X = X.fillna(0)

        # Generate predictions
        predictions = model.predict(X).tolist()

        # Probabilities and confidence
        probabilities = None
        confidence_scores = []
        risk_levels = []

        if feature_config.task == ModelTask.CLASSIFICATION:
            if hasattr(model, "predict_proba"):
                prob_array = model.predict_proba(X)[:, 1]
                probabilities = prob_array.tolist()
                conf_result = compute_classification_confidence(prob_array)
                confidence_scores = conf_result.confidence_scores
                risk_levels = [_classify_risk(p) for p in prob_array]
            else:
                confidence_scores = [0.5] * len(predictions)
                risk_levels = [_classify_risk(float(p)) for p in predictions]
        else:
            conf_result = compute_regression_confidence(np.array(predictions))
            confidence_scores = conf_result.confidence_scores

        prediction_time_ms = (time.perf_counter() - start_time) * 1000

        result = PredictionResult(
            intelligence_type=intelligence_type.value,
            model_version=model_version,
            predictions=predictions,
            probabilities=probabilities,
            confidence_scores=confidence_scores,
            risk_levels=risk_levels,
            mean_confidence=float(np.mean(confidence_scores)) if confidence_scores else 0.0,
            n_predictions=len(predictions),
            prediction_time_ms=prediction_time_ms,
            metadata={
                "features_used": available_features,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            f"Prediction complete: {intelligence_type.value} "
            f"n={len(predictions)} time={prediction_time_ms:.1f}ms"
        )
        return result

    def predict_single(
        self,
        record: dict[str, Any],
        intelligence_type: IntelligenceType,
        version_id: str | None = None,
    ) -> PredictionRecord:
        """Generate prediction for a single record."""
        df = pd.DataFrame([record])
        result = self.predict(df, intelligence_type, version_id)

        return PredictionRecord(
            prediction=result.predictions[0],
            probability=result.probabilities[0] if result.probabilities else None,
            confidence=result.confidence_scores[0] if result.confidence_scores else 0.0,
            risk_level=result.risk_levels[0] if result.risk_levels else "",
        )


class DemandAgent:
    """Demand Agent - deterministic ML service to predict future demand."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.DEMAND, version_id)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.DEMAND, version_id)


class InventoryAgent:
    """Inventory Agent - deterministic ML service to predict inventory stress."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.INVENTORY, version_id)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.INVENTORY, version_id)


class SupplierAgent:
    """Supplier Agent - deterministic ML service to predict supplier reliability and late delivery risk."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.SUPPLIER, version_id)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.SUPPLIER, version_id)


class LogisticsAgent:
    """Logistics Agent - deterministic ML service to predict logistics and shipment delays."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.LOGISTICS, version_id)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.LOGISTICS, version_id)


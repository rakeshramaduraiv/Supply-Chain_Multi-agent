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
    confidence_lower: list[float] = field(default_factory=list)
    confidence_upper: list[float] = field(default_factory=list)
    graph_context_used: bool = False
    graph_amplification: dict[str, Any] = field(default_factory=dict)

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
        graph_context: dict[str, Any] | None = None,
    ) -> PredictionResult:
        """
        Generate predictions for a dataframe.

        Args:
            df: Input dataframe with required features
            intelligence_type: Which intelligence model to use
            version_id: Specific model version (None = latest)
            graph_context: Live Knowledge Graph context from GraphRAG.
                           Contains supplier reliability, inventory stress,
                           upcoming calendar events, and TPKE inferred
                           edge signals. Injected as 4 model features and
                           used to apply domain-specific risk amplification.
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

        # ── GRAPH CONTEXT INJECTION ────────────────────────────────
        X = self._inject_graph_context(X, graph_context)

        # Handle missing features by filling with 0
        for feat in feature_config.features:
            if feat not in X.columns:
                X[feat] = 0

        X = X[feature_config.features]
        X = X.fillna(0)

        # Generate raw model outputs
        predictions = model.predict(X).tolist()

        # Probabilities and confidence
        probabilities = None
        confidence_scores = []
        risk_levels = []
        amplification_applied: dict[str, Any] = {"amplified": False, "factor": 1.0, "reason": None}

        if feature_config.task == ModelTask.CLASSIFICATION:
            if hasattr(model, "predict_proba"):
                prob_array = model.predict_proba(X)[:, 1]

                # ── GRAPH AMPLIFICATION on probabilities (classifiers) ──
                # Amplification is applied to P(risk=1) before thresholding,
                # not to the binary label — multiplying 0/1 by a factor is
                # meaningless and produces out-of-range values.
                prob_list, amplification_applied = self._apply_graph_amplification(
                    prob_array.tolist(), intelligence_type, graph_context
                )
                prob_array_amp = np.clip(np.array(prob_list), 0.0, 1.0)

                probabilities = prob_array_amp.tolist()
                predictions = (prob_array_amp >= 0.5).astype(int).tolist()
                conf_result = compute_classification_confidence(prob_array_amp)
                confidence_scores = conf_result.confidence_scores
                risk_levels = [_classify_risk(p) for p in prob_array_amp]
            else:
                confidence_scores = [0.5] * len(predictions)
                risk_levels = [_classify_risk(float(p)) for p in predictions]
        else:
            # ── GRAPH AMPLIFICATION on demand forecast (regressor) ──
            predictions, amplification_applied = self._apply_graph_amplification(
                predictions, intelligence_type, graph_context
            )
            conf_result = compute_regression_confidence(np.array(predictions))
            confidence_scores = conf_result.confidence_scores

        # Volatility-adjusted 95% prediction interval (regression only)
        if feature_config.task == ModelTask.REGRESSION:
            volatility = float(graph_context.get("demand_volatility", 0.30)) if graph_context else 0.30
            ci_pct = max(0.10, min(0.40, volatility * 0.5))
            confidence_lower = [round(p * (1 - ci_pct), 4) for p in predictions]
            confidence_upper = [round(p * (1 + ci_pct), 4) for p in predictions]
        else:
            confidence_lower = []
            confidence_upper = []

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
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            graph_context_used=graph_context is not None,
            graph_amplification=amplification_applied,
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

    @staticmethod
    def _inject_graph_context(
        X: pd.DataFrame, graph_context: dict[str, Any] | None
    ) -> pd.DataFrame:
        """
        Maps GraphRAG internal names -> model feature names (graph_ prefix).
        See CLAUDE.md section 5 "GraphRAG Context Naming Convention" for the
        full two-stage transformation: avg_* (Neo4j) -> graph_* (ML model).

        The 4 graph_* columns exist at training time with neutral defaults.
        At prediction time they are overwritten with live Neo4j values.
        """
        X = X.copy()
        if graph_context:
            X["graph_supplier_reliability"] = float(graph_context.get("avg_supplier_reliability", 0.5))
            X["graph_inventory_stress"]      = float(graph_context.get("inventory_stress", 0.5))
            X["graph_has_upcoming_event"]    = int(bool(graph_context.get("upcoming_events")))
            X["graph_avg_shipping_delay"]    = float(graph_context.get("avg_shipping_delay", 0.0))
        else:
            X["graph_supplier_reliability"] = 0.5
            X["graph_inventory_stress"]     = 0.5
            X["graph_has_upcoming_event"]   = 0
            X["graph_avg_shipping_delay"]   = 0.0
        return X

    @staticmethod
    def _apply_graph_amplification(
        predictions: list[float],
        intelligence_type: IntelligenceType,
        graph_context: dict[str, Any] | None,
    ) -> tuple[list[float], dict[str, Any]]:
        """
        Applies domain-specific risk amplification driven by KG signals
        including TPKE inferred edges.

        DEMAND:    calendar events boost forecast volume
        INVENTORY: low supplier reliability amplifies stockout risk
        SUPPLIER:  TPKE demand-spike edges amplify delay risk
        LOGISTICS: no amplification (route delay is direct)
        """
        applied: dict[str, Any] = {"amplified": False, "factor": 1.0, "reason": None}
        if not graph_context:
            return predictions, applied

        factor = 1.0
        reason = []

        if intelligence_type == IntelligenceType.DEMAND:
            if graph_context.get("upcoming_events"):
                factor *= 1.25
                reason.append("calendar_event_boost")
            if graph_context.get("holiday_risk_events"):
                factor *= 1.15
                reason.append("tpke_seasonal_edge")

        elif intelligence_type == IntelligenceType.INVENTORY:
            if float(graph_context.get("avg_supplier_reliability", 1.0)) < 0.5:
                factor *= 1.30
                reason.append("low_supplier_reliability")
            if graph_context.get("holiday_risk_events"):
                factor *= 1.20
                reason.append("tpke_seasonal_stockout_edge")

        elif intelligence_type == IntelligenceType.SUPPLIER:
            if int(graph_context.get("amplified_supplier_count", 0)) > 0:
                factor *= 1.20
                reason.append("tpke_demand_spike_edge")

        if factor != 1.0:
            predictions = [float(p) * factor for p in predictions]
            applied = {"amplified": True, "factor": round(factor, 3), "reason": ",".join(reason)}

        return predictions, applied

    def predict_single(
        self,
        record: dict[str, Any],
        intelligence_type: IntelligenceType,
        version_id: str | None = None,
        graph_context: dict[str, Any] | None = None,
    ) -> PredictionRecord:
        """Generate prediction for a single record."""
        df = pd.DataFrame([record])
        result = self.predict(df, intelligence_type, version_id, graph_context)

        return PredictionRecord(
            prediction=result.predictions[0],
            probability=result.probabilities[0] if result.probabilities else None,
            confidence=result.confidence_scores[0] if result.confidence_scores else 0.0,
            risk_level=result.risk_levels[0] if result.risk_levels else "",
        )


class DemandAgent:
    """Demand Agent - predicts future demand quantity."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.DEMAND, version_id, graph_context)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.DEMAND, version_id, graph_context)


class InventoryAgent:
    """Inventory Agent - predicts stockout risk."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.INVENTORY, version_id, graph_context)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.INVENTORY, version_id, graph_context)


class SupplierAgent:
    """Supplier Agent - predicts late delivery risk."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.SUPPLIER, version_id, graph_context)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.SUPPLIER, version_id, graph_context)


class LogisticsAgent:
    """Logistics Agent - predicts route-level delivery delay risk."""
    def __init__(self, registry: ModelRegistry | None = None):
        self.engine = PredictionEngine(registry)

    def predict(self, df: pd.DataFrame, version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionResult:
        return self.engine.predict(df, IntelligenceType.LOGISTICS, version_id, graph_context)

    def predict_single(self, record: dict[str, Any], version_id: str | None = None, graph_context: dict[str, Any] | None = None) -> PredictionRecord:
        return self.engine.predict_single(record, IntelligenceType.LOGISTICS, version_id, graph_context)


# Lazy import helper to avoid circular dependency
def get_collaborative_pipeline(registry: ModelRegistry | None = None):
    from app.ml.prediction.collaborative_pipeline import CollaborativeAgentPipeline
    return CollaborativeAgentPipeline(registry)


# Aliases for test compatibility (CLAUDE.md section 11)
DemandPredictor    = DemandAgent
InventoryPredictor = InventoryAgent
SupplierPredictor  = SupplierAgent
LogisticsPredictor = LogisticsAgent


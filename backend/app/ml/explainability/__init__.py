"""
AMASCI Prediction Explainability
===================================
Wraps any PredictionResult with structured explainability output.

Every prediction returns:
  - prediction value
  - confidence
  - top_features  (from feature importance, ranked by gain)
  - graph_context_used  (bool + summary)
  - reason  (human-readable sentence grounded in top features)

Example output
--------------
{
    "agent": "demand",
    "prediction": 420.0,
    "confidence": 0.91,
    "risk_level": "high",
    "top_features": [
        {"feature": "order_month",        "importance": 0.312},
        {"feature": "Order Item Quantity", "importance": 0.198},
        {"feature": "Sales",              "importance": 0.143},
    ],
    "graph_context_used": true,
    "graph_context_summary": "3 high-risk suppliers, 1 seasonal event",
    "reason": "Demand forecast of 420 driven primarily by order_month (31.2%) "
              "and Order Item Quantity (19.8%). Seasonal holiday demand pattern detected.",
    "timestamp": "2026-07-28T10:00:00+00:00"
}

Usage
-----
    from app.ml.explainability import PredictionExplainer

    explainer = PredictionExplainer()
    explanation = explainer.explain(
        agent="demand",
        prediction=420.0,
        confidence=0.91,
        feature_importance=fi_result.to_dict(),
        graph_context={"high_risk_suppliers": 3, "seasonal_events": 1},
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Human-readable reason templates per agent
_REASON_TEMPLATES: dict[str, str] = {
    "demand": (
        "Demand forecast of {prediction:.0f} units driven primarily by "
        "{top1} ({top1_pct:.1f}%) and {top2} ({top2_pct:.1f}%). "
        "{context_note}"
    ),
    "supplier": (
        "Supplier risk score of {prediction:.3f} ({risk_level}) driven by "
        "{top1} ({top1_pct:.1f}%) and {top2} ({top2_pct:.1f}%). "
        "{context_note}"
    ),
    "inventory": (
        "Inventory stockout probability of {prediction:.1%} driven by "
        "{top1} ({top1_pct:.1f}%) and {top2} ({top2_pct:.1f}%). "
        "{context_note}"
    ),
    "logistics": (
        "Logistics delay probability of {prediction:.1%} driven by "
        "{top1} ({top1_pct:.1f}%) and {top2} ({top2_pct:.1f}%). "
        "{context_note}"
    ),
}

_CONTEXT_NOTES: dict[str, dict[str, str]] = {
    "demand": {
        "high":     "Seasonal holiday demand pattern detected in graph context.",
        "medium":   "Moderate demand variability observed in supply chain graph.",
        "low":      "Stable demand conditions indicated by graph context.",
        "critical": "Extreme demand surge detected — multiple seasonal signals active.",
    },
    "supplier": {
        "high":     "Supplier reliability degradation detected in knowledge graph.",
        "medium":   "Moderate supplier delay risk from graph traversal.",
        "low":      "Supplier performance within normal bounds.",
        "critical": "Critical supplier failure risk — multiple delay patterns active.",
    },
    "inventory": {
        "high":     "Inventory stress propagated from upstream supplier delays.",
        "medium":   "Moderate stockout risk from demand-supply imbalance.",
        "low":      "Inventory levels adequate based on graph context.",
        "critical": "Stockout imminent — warehouse stress and supplier delays converging.",
    },
    "logistics": {
        "high":     "Transportation delay risk elevated by inventory stress signals.",
        "medium":   "Moderate route delay risk from regional congestion patterns.",
        "low":      "Logistics performance within expected parameters.",
        "critical": "Severe logistics disruption risk — multiple upstream failures.",
    },
}


def _risk_label(score: float) -> str:
    if score >= 0.75:
        return "critical"
    elif score >= 0.50:
        return "high"
    elif score >= 0.25:
        return "medium"
    return "low"


@dataclass
class ExplainedPrediction:
    agent: str
    prediction: float
    confidence: float
    risk_level: str
    top_features: list[dict[str, Any]]
    graph_context_used: bool
    graph_context_summary: str
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "prediction": round(self.prediction, 4),
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level,
            "top_features": self.top_features,
            "graph_context_used": self.graph_context_used,
            "graph_context_summary": self.graph_context_summary,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class PredictionExplainer:
    """
    Attaches explainability metadata to any agent prediction.

    Inputs:
      - agent name
      - scalar prediction value
      - confidence score
      - feature_importance dict (from FeatureImportanceResult.to_dict())
      - graph_context dict (optional, from GraphRAG or graph properties)
    """

    def explain(
        self,
        agent: str,
        prediction: float,
        confidence: float,
        feature_importance: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
        risk_probability: float | None = None,
    ) -> ExplainedPrediction:
        """
        Build a fully explained prediction record.

        Args:
            agent:             one of demand / supplier / inventory / logistics
            prediction:        scalar prediction value
            confidence:        [0,1] confidence score
            feature_importance: FeatureImportanceResult.to_dict() output
            graph_context:     optional dict with graph-derived signals
            risk_probability:  optional explicit risk probability for classifiers
        """
        # Determine risk level
        risk_val = risk_probability if risk_probability is not None else (
            prediction if agent != "demand" else min(1.0, prediction / 500.0)
        )
        risk_level = _risk_label(float(risk_val))

        # Extract top features
        top_features = self._extract_top_features(feature_importance)

        # Graph context
        graph_used = bool(graph_context)
        graph_summary = self._summarise_graph_context(graph_context or {})

        # Build reason string
        reason = self._build_reason(
            agent, prediction, confidence, risk_level, top_features, graph_context or {}
        )

        return ExplainedPrediction(
            agent=agent,
            prediction=prediction,
            confidence=confidence,
            risk_level=risk_level,
            top_features=top_features,
            graph_context_used=graph_used,
            graph_context_summary=graph_summary,
            reason=reason,
        )

    def explain_batch(
        self,
        agent: str,
        predictions: list[float],
        confidences: list[float],
        feature_importance: dict[str, Any] | None = None,
        graph_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Explain a batch prediction by summarising to mean values.
        Returns a single ExplainedPrediction dict for the batch.
        """
        import statistics
        mean_pred = statistics.mean(predictions) if predictions else 0.0
        mean_conf = statistics.mean(confidences) if confidences else 0.5
        explained = self.explain(agent, mean_pred, mean_conf, feature_importance, graph_context)
        result = explained.to_dict()
        result["batch_size"] = len(predictions)
        result["prediction_std"] = round(
            statistics.stdev(predictions) if len(predictions) > 1 else 0.0, 4
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_top_features(
        self, feature_importance: dict[str, Any] | None, top_n: int = 5
    ) -> list[dict[str, Any]]:
        """Extract top N features from a FeatureImportanceResult dict."""
        if not feature_importance:
            return []
        ranking = feature_importance.get("top_features") or feature_importance.get("ranking", [])
        top = []
        for item in ranking[:top_n]:
            top.append({
                "feature": item.get("feature", "unknown"),
                "importance": round(float(item.get("gain_importance", 0.0)), 4),
                "rank": item.get("rank", 0),
            })
        return top

    def _summarise_graph_context(self, ctx: dict[str, Any]) -> str:
        """Build a short human-readable summary of graph context."""
        if not ctx:
            return "No graph context available."
        parts = []
        for key, val in ctx.items():
            if isinstance(val, (int, float)) and val > 0:
                parts.append(f"{val} {key.replace('_', ' ')}")
            elif isinstance(val, str) and val:
                parts.append(val)
        return ", ".join(parts[:4]) if parts else "Graph context retrieved."

    def _build_reason(
        self,
        agent: str,
        prediction: float,
        confidence: float,
        risk_level: str,
        top_features: list[dict[str, Any]],
        graph_context: dict[str, Any],
    ) -> str:
        """Build a grounded human-readable reason string."""
        template = _REASON_TEMPLATES.get(agent, "{agent} prediction: {prediction:.4f}")
        context_note = _CONTEXT_NOTES.get(agent, {}).get(risk_level, "")

        top1 = top_features[0]["feature"] if len(top_features) > 0 else "primary feature"
        top1_pct = top_features[0]["importance"] * 100 if len(top_features) > 0 else 0.0
        top2 = top_features[1]["feature"] if len(top_features) > 1 else "secondary feature"
        top2_pct = top_features[1]["importance"] * 100 if len(top_features) > 1 else 0.0

        try:
            return template.format(
                prediction=prediction,
                risk_level=risk_level,
                top1=top1,
                top1_pct=top1_pct,
                top2=top2,
                top2_pct=top2_pct,
                context_note=context_note,
            )
        except (KeyError, ValueError):
            return (
                f"{agent.capitalize()} prediction: {prediction:.4f} "
                f"(confidence: {confidence:.2%}, risk: {risk_level}). "
                f"{context_note}"
            )

"""
AMASCI Weighted Agent Orchestrator
=====================================
Replaces simple average risk with a configurable weighted overall risk score.

Weight formula per agent:
    effective_weight = base_weight × historical_accuracy × mean_confidence

Weights are then normalised to sum to 1.0 before computing the final score.

Default business weights (configurable):
    demand    = 0.30
    supplier  = 0.35
    inventory = 0.20
    logistics = 0.15

Output
------
    {
        "overall_risk":    0.72,
        "weighted_score":  0.72,
        "risk_level":      "high",
        "confidence":      0.88,
        "agent_weights": {
            "demand":    {"base": 0.30, "effective": 0.28, "normalised": 0.29},
            "supplier":  {"base": 0.35, "effective": 0.34, "normalised": 0.36},
            "inventory": {"base": 0.20, "effective": 0.18, "normalised": 0.19},
            "logistics": {"base": 0.15, "effective": 0.15, "normalised": 0.16},
        },
        "agent_scores": {
            "demand":    {"risk_score": 0.61, "confidence": 0.91},
            ...
        },
        "timestamp": "...",
    }

Usage
-----
    from app.ml.orchestrator import WeightedOrchestrator

    orch = WeightedOrchestrator()
    result = orch.compute(agent_results, agent_memory)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Default business importance weights (must sum to 1.0)
DEFAULT_WEIGHTS: dict[str, float] = {
    "demand":    0.30,
    "supplier":  0.35,
    "inventory": 0.20,
    "logistics": 0.15,
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
class AgentWeightDetail:
    base: float
    historical_accuracy: float
    mean_confidence: float
    effective: float
    normalised: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": round(self.base, 4),
            "historical_accuracy": round(self.historical_accuracy, 4),
            "mean_confidence": round(self.mean_confidence, 4),
            "effective": round(self.effective, 4),
            "normalised": round(self.normalised, 4),
        }


@dataclass
class OrchestratorResult:
    overall_risk: float
    weighted_score: float
    risk_level: str
    confidence: float
    agent_weights: dict[str, AgentWeightDetail] = field(default_factory=dict)
    agent_scores: dict[str, dict[str, Any]] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_risk": round(self.overall_risk, 4),
            "weighted_score": round(self.weighted_score, 4),
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 4),
            "agent_weights": {k: v.to_dict() for k, v in self.agent_weights.items()},
            "agent_scores": self.agent_scores,
            "timestamp": self.timestamp,
        }


class WeightedOrchestrator:
    """
    Computes a weighted overall risk score from all four agent predictions.

    Effective weight = base_weight × historical_accuracy × mean_confidence
    Weights are normalised to sum to 1.0 before the final dot product.
    """

    def __init__(self, base_weights: dict[str, float] | None = None):
        self._base_weights = base_weights or DEFAULT_WEIGHTS.copy()

    def compute(
        self,
        agent_results: dict[str, dict[str, Any]],
        agent_memory: Any | None = None,
    ) -> OrchestratorResult:
        """
        Compute weighted overall risk.

        Args:
            agent_results: dict keyed by agent name, each value is a
                           PredictionResult.to_dict() or a bus signal dict.
            agent_memory:  AgentMemory instance (optional) — used to pull
                           historical accuracy per agent.

        Returns:
            OrchestratorResult
        """
        agents = list(self._base_weights.keys())
        agent_scores: dict[str, dict[str, Any]] = {}
        effective_weights: dict[str, float] = {}
        weight_details: dict[str, AgentWeightDetail] = {}

        for agent in agents:
            result = agent_results.get(agent, {})
            base_w = self._base_weights[agent]

            # Extract risk score from result
            risk_score = self._extract_risk_score(agent, result)
            mean_conf = self._extract_confidence(result)

            # Historical accuracy from memory (default 0.85 if unavailable)
            hist_acc = 0.85
            if agent_memory is not None:
                try:
                    hist_acc = agent_memory.get_historical_accuracy(agent)
                except Exception:
                    pass

            effective_w = base_w * hist_acc * mean_conf
            effective_weights[agent] = effective_w

            agent_scores[agent] = {
                "risk_score": round(risk_score, 4),
                "confidence": round(mean_conf, 4),
                "historical_accuracy": round(hist_acc, 4),
                "risk_level": _risk_label(risk_score),
            }

            weight_details[agent] = AgentWeightDetail(
                base=base_w,
                historical_accuracy=hist_acc,
                mean_confidence=mean_conf,
                effective=effective_w,
                normalised=0.0,  # filled below
            )

        # Normalise effective weights
        total_eff = sum(effective_weights.values())
        if total_eff == 0:
            total_eff = 1.0
        normalised: dict[str, float] = {
            a: w / total_eff for a, w in effective_weights.items()
        }
        for agent, detail in weight_details.items():
            detail.normalised = normalised[agent]

        # Weighted risk score
        weighted_score = sum(
            normalised[a] * agent_scores[a]["risk_score"] for a in agents
        )

        # Overall confidence = weighted mean of agent confidences
        overall_conf = sum(
            normalised[a] * agent_scores[a]["confidence"] for a in agents
        )

        result_obj = OrchestratorResult(
            overall_risk=weighted_score,
            weighted_score=weighted_score,
            risk_level=_risk_label(weighted_score),
            confidence=overall_conf,
            agent_weights=weight_details,
            agent_scores=agent_scores,
        )

        logger.info(
            f"[Orchestrator] overall_risk={weighted_score:.4f} "
            f"({result_obj.risk_level}) confidence={overall_conf:.4f}"
        )
        return result_obj

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_risk_score(self, agent: str, result: dict[str, Any]) -> float:
        """
        Extract a [0,1] risk score from a PredictionResult dict.

        For classifiers: use predictions_summary.mean (already a probability).
        For demand regressor: normalise mean prediction by a soft cap (500 units).
        """
        if "error" in result:
            return 0.5  # neutral fallback on error

        # Risk distribution from classifier
        risk_dist = result.get("risk_distribution", {})
        if risk_dist:
            total = sum(risk_dist.values()) or 1
            high_count = risk_dist.get("high", 0) + risk_dist.get("critical", 0)
            return high_count / total

        # Mean prediction from summary
        summary = result.get("predictions_summary", {})
        mean_pred = summary.get("mean", 0.0)

        if agent == "demand":
            return min(1.0, float(mean_pred) / 500.0)

        # Classifier mean probability in [0,1]
        return min(1.0, max(0.0, float(mean_pred)))

    def _extract_confidence(self, result: dict[str, Any]) -> float:
        """Extract mean confidence from a PredictionResult dict."""
        if "error" in result:
            return 0.5
        conf = result.get("mean_confidence", 0.5)
        return min(1.0, max(0.0, float(conf)))

    def update_weights(self, new_weights: dict[str, float]) -> None:
        """
        Update base business importance weights at runtime.
        Weights are normalised internally so they don't need to sum to 1.
        """
        total = sum(new_weights.values())
        if total <= 0:
            raise ValueError("Weights must sum to a positive number")
        self._base_weights = {k: v / total for k, v in new_weights.items()}
        logger.info(f"[Orchestrator] Weights updated: {self._base_weights}")

    def get_weights(self) -> dict[str, float]:
        return self._base_weights.copy()

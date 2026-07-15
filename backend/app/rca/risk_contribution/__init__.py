"""
AMASCI RCA Risk Contribution Engine
======================================
Weighted contribution scoring for root cause ranking.

Formula:
    RiskContribution = α×NodeRisk + β×RelationshipWeight + γ×TPKEEdgeWeight
                     + δ×CentralityScore + ε×ForecastConfidence
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.rca.utils import (
    ALPHA, BETA, GAMMA, DELTA, EPSILON,
    PerformanceTimer, compute_risk_label, extract_node_risk,
    extract_relationship_weight, normalize_scores,
)

logger = logging.getLogger(__name__)


@dataclass
class ContributionScore:
    """Risk contribution score for a single node."""
    node_id: str
    label: str
    total_score: float = 0.0
    node_risk: float = 0.0
    relationship_weight: float = 0.0
    tpke_weight: float = 0.0
    centrality_score: float = 0.0
    forecast_confidence: float = 0.0
    risk_level: str = "low"
    rank: int = 0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "total_score": round(self.total_score, 4),
            "components": {
                "node_risk": round(self.node_risk, 4),
                "relationship_weight": round(self.relationship_weight, 4),
                "tpke_weight": round(self.tpke_weight, 4),
                "centrality_score": round(self.centrality_score, 4),
                "forecast_confidence": round(self.forecast_confidence, 4),
            },
            "risk_level": self.risk_level,
            "rank": self.rank,
        }


@dataclass
class ContributionResult:
    """Result of risk contribution analysis."""
    target_id: str
    rca_type: str
    contributors: list[ContributionScore] = field(default_factory=list)
    total_risk_exposure: float = 0.0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "rca_type": self.rca_type,
            "contributors": [c.to_dict() for c in self.contributors],
            "total_risk_exposure": round(self.total_risk_exposure, 4),
            "top_contributor": self.contributors[0].to_dict() if self.contributors else None,
            "duration_ms": round(self.duration_ms, 2),
        }


class RiskContributionEngine:
    """
    Computes weighted risk contribution scores for candidate root cause nodes.

    Formula:
        Score = α×NodeRisk + β×RelWeight + γ×TPKEWeight + δ×Centrality + ε×ForecastConf

    Where:
        α=0.30, β=0.25, γ=0.20, δ=0.15, ε=0.10
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def compute_contributions(
        self,
        target_id: str,
        target_label: str,
        candidate_nodes: list[dict[str, Any]],
        rca_type: str,
        top_n: int = 10,
    ) -> ContributionResult:
        """Compute risk contribution for all candidate nodes."""
        with PerformanceTimer("compute_contributions") as timer:
            scores: list[ContributionScore] = []

            for candidate in candidate_nodes:
                node_id = candidate.get("node_id", "")
                label = candidate.get("label", "Unknown")
                properties = candidate.get("properties", candidate)

                score = await self._score_candidate(
                    target_id, target_label, node_id, label, properties, rca_type
                )
                scores.append(score)

            # Sort by total score descending
            scores.sort(key=lambda s: s.total_score, reverse=True)

            # Assign ranks
            for i, s in enumerate(scores):
                s.rank = i + 1

            # Trim to top_n
            top_scores = scores[:top_n]
            total_exposure = sum(s.total_score for s in top_scores)

        return ContributionResult(
            target_id=target_id,
            rca_type=rca_type,
            contributors=top_scores,
            total_risk_exposure=total_exposure,
            duration_ms=timer.duration_ms,
        )

    async def _score_candidate(
        self,
        target_id: str,
        target_label: str,
        node_id: str,
        label: str,
        properties: dict[str, Any],
        rca_type: str,
    ) -> ContributionScore:
        """Compute the full contribution score for a single candidate."""
        # Component 1: Node Risk
        node_risk = extract_node_risk(properties)

        # Component 2: Relationship Weight (to target)
        rel_weight = await self._get_relationship_weight(node_id, target_id)

        # Component 3: TPKE Edge Weight
        tpke_weight = await self._get_tpke_weight(node_id, target_id)

        # Component 4: Centrality Score
        centrality = await self._get_centrality(node_id, label)

        # Component 5: Forecast Confidence (context-dependent)
        forecast_conf = self._get_forecast_confidence(properties, rca_type)

        # Weighted sum
        total = (
            ALPHA * node_risk
            + BETA * rel_weight
            + GAMMA * tpke_weight
            + DELTA * centrality
            + EPSILON * forecast_conf
        )

        return ContributionScore(
            node_id=node_id,
            label=label,
            total_score=total,
            node_risk=node_risk,
            relationship_weight=rel_weight,
            tpke_weight=tpke_weight,
            centrality_score=centrality,
            forecast_confidence=forecast_conf,
            risk_level=compute_risk_label(total),
            properties=properties,
        )

    async def _get_relationship_weight(self, source_id: str, target_id: str) -> float:
        """Get relationship weight between two nodes."""
        query = """
            MATCH (a {node_id: $source_id})-[r]-(b {node_id: $target_id})
            RETURN coalesce(r.relationship_strength, 0.5) AS weight
            LIMIT 1
        """
        records = await self._conn.execute_query(
            query, {"source_id": source_id, "target_id": target_id}
        )
        if records:
            return float(records[0]["weight"])
        # No direct relationship - check 2-hop proximity
        query_2hop = """
            MATCH path = (a {node_id: $source_id})-[*1..2]-(b {node_id: $target_id})
            RETURN 0.3 AS weight
            LIMIT 1
        """
        records_2 = await self._conn.execute_query(
            query_2hop, {"source_id": source_id, "target_id": target_id}
        )
        return float(records_2[0]["weight"]) if records_2 else 0.1

    async def _get_tpke_weight(self, source_id: str, target_id: str) -> float:
        """Get TPKE-inferred edge weight (edges with tpke_inferred property)."""
        query = """
            MATCH (a {node_id: $source_id})-[r]-(b {node_id: $target_id})
            WHERE r.tpke_inferred = true OR r.tpke_confidence IS NOT NULL
            RETURN coalesce(r.tpke_confidence, r.relationship_strength, 0.5) AS weight
            LIMIT 1
        """
        records = await self._conn.execute_query(
            query, {"source_id": source_id, "target_id": target_id}
        )
        return float(records[0]["weight"]) if records else 0.0

    async def _get_centrality(self, node_id: str, label: str) -> float:
        """Compute degree-based centrality for a node."""
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})-[r]-()
            WITH count(r) AS degree
            OPTIONAL MATCH (m:{label})-[r2]-()
            WITH degree, count(DISTINCT m) AS total_nodes
            RETURN CASE WHEN total_nodes > 1
                        THEN toFloat(degree) / toFloat(total_nodes - 1)
                        ELSE 0.0 END AS centrality
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        if records:
            return min(1.0, float(records[0]["centrality"]))
        return 0.0

    def _get_forecast_confidence(self, properties: dict[str, Any], rca_type: str) -> float:
        """Extract forecast-related confidence from node properties."""
        if rca_type in ("demand_spike", "inventory_stress"):
            volatility = properties.get("demand_volatility", 0.0)
            if isinstance(volatility, (int, float)):
                return min(1.0, float(volatility))
        if rca_type in ("late_delivery", "shipping_delay"):
            delay_rate = properties.get("late_delivery_rate", properties.get("supplier_delay_rate", 0.0))
            if isinstance(delay_rate, (int, float)):
                return min(1.0, float(delay_rate))
        if rca_type == "supplier_failure":
            reliability = properties.get("supplier_reliability_score", 1.0)
            if isinstance(reliability, (int, float)):
                return max(0.0, 1.0 - float(reliability))
        return 0.0

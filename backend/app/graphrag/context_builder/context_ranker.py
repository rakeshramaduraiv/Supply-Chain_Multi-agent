"""
AMASCI GraphRAG Context Ranker
================================
Ranks retrieved graph context items (nodes, relationships, predictions, RCA chains, actuals)
using a composite scoring formula across 5 dimensions:

    Score = w1·Centrality + w2·EdgeConfidence + w3·PredictionConfidence + w4·Recency + w5·RiskImportance
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RankedContextItem:
    """A ranked item of graph context."""
    item_id: str
    item_type: str         # "node" | "relationship" | "prediction" | "rca_event" | "actual_upload"
    title: str
    score: float
    confidence: float
    recency_score: float
    risk_importance: float
    details: dict[str, Any] = field(default_factory=dict)


class ContextRanker:
    """
    Ranks retrieved context elements to select Top-K most relevant items for LLM prompts.
    """

    def __init__(
        self,
        w_centrality: float = 0.20,
        w_edge_confidence: float = 0.25,
        w_pred_confidence: float = 0.20,
        w_recency: float = 0.15,
        w_risk_importance: float = 0.20,
    ):
        self.w1 = w_centrality
        self.w2 = w_edge_confidence
        self.w3 = w_pred_confidence
        self.w4 = w_recency
        self.w5 = w_risk_importance

    def rank_context(
        self,
        raw_items: list[dict[str, Any]],
        top_k: int = 15,
        reference_time: datetime | None = None,
    ) -> list[RankedContextItem]:
        """
        Rank raw retrieved graph items and return Top-K.
        """
        if not raw_items:
            return []

        ref = reference_time or datetime.now(timezone.utc)
        ranked: list[RankedContextItem] = []

        for item in raw_items:
            item_type = item.get("item_type", "node")
            props = item.get("properties", {}) or item

            # 1. Centrality (degree or total_orders / total_shipments)
            centrality = float(props.get("degree", 0.5) or props.get("total_orders", 10) / 100.0)
            centrality = min(max(centrality, 0.1), 1.0)

            # 2. Edge confidence / TPKE weight
            edge_conf = float(props.get("confidence", 0.5) or props.get("weight", 0.5))

            # 3. Prediction confidence
            pred_conf = float(props.get("prediction_confidence", 0.8) or 0.8)

            # 4. Recency score (days elapsed since last_updated / timestamp)
            ts_str = props.get("last_updated") or props.get("timestamp") or props.get("created_at")
            recency = 0.5
            if ts_str:
                try:
                    ts = datetime.fromisoformat(str(ts_str))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    days = (ref - ts).total_seconds() / 86400.0
                    recency = max(0.1, 1.0 - (days / 90.0))
                except Exception:
                    recency = 0.5

            # 5. Risk importance
            risk = float(props.get("risk_score", 0.5) or props.get("late_delivery_risk", 0.5) or 0.5)

            # Composite Score
            score = (
                self.w1 * centrality
                + self.w2 * edge_conf
                + self.w3 * pred_conf
                + self.w4 * recency
                + self.w5 * risk
            )
            score = round(min(max(score, 0.0), 1.0), 4)

            title = str(props.get("name") or props.get("node_id") or props.get("relationship_type") or "Graph Element")

            ranked.append(RankedContextItem(
                item_id=str(item.get("item_id") or props.get("node_id") or title),
                item_type=item_type,
                title=title,
                score=score,
                confidence=round(edge_conf, 4),
                recency_score=round(recency, 4),
                risk_importance=round(risk, 4),
                details=props,
            ))

        ranked.sort(key=lambda x: x.score, reverse=True)
        return ranked[:top_k]

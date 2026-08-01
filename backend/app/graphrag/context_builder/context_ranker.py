"""
AMASCI GraphRAG Evidence Ranker
==================================
Ranks retrieved graph nodes across 6 factors:
1. Centrality (degree / connectivity)
2. Recency (timestamp freshness)
3. Prediction Confidence (model confidence)
4. TPKE Confidence (learned edge weight / confidence)
5. Business Importance (entity label priority weight)
6. Similarity to User Question (lexical/semantic query match)

Formula:
  Score = 0.15·Centrality + 0.15·Recency + 0.15·PredConf + 0.20·TPKEConf + 0.15·BusinessImportance + 0.20·QuerySimilarity

Returns Top-K highest ranked evidence with explicit ranking scores for every node.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FactorScores:
    """Detailed score breakdown across all 7 ranking factors."""
    query_similarity: float
    node_centrality: float
    business_importance: float
    prediction_confidence: float
    tpke_confidence: float
    recency: float
    root_cause_contribution: float

    def to_dict(self) -> dict[str, float]:
        return {
            "query_similarity": round(self.query_similarity, 4),
            "node_centrality": round(self.node_centrality, 4),
            "business_importance": round(self.business_importance, 4),
            "prediction_confidence": round(self.prediction_confidence, 4),
            "tpke_confidence": round(self.tpke_confidence, 4),
            "recency": round(self.recency, 4),
            "root_cause_contribution": round(self.root_cause_contribution, 4),
        }


@dataclass
class RankedContextItem:
    """A ranked item of graph evidence."""
    item_id: str
    item_type: str         # "node" | "relationship" | "prediction" | "rca_event" | "actual_upload"
    title: str
    total_score: float
    confidence: float
    recency_score: float
    risk_importance: float
    factor_scores: FactorScores
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "title": self.title,
            "total_score": round(self.total_score, 4),
            "confidence": round(self.confidence, 4),
            "recency_score": round(self.recency_score, 4),
            "risk_importance": round(self.risk_importance, 4),
            "factor_scores": self.factor_scores.to_dict(),
            "details": self.details,
        }


class ContextRanker:
    """
    Ranks retrieved context elements across 7 weighted factors to select Top-K evidence.
    """

    def __init__(
        self,
        w_query_similarity: float = 0.20,
        w_node_centrality: float = 0.15,
        w_business_importance: float = 0.15,
        w_prediction_confidence: float = 0.15,
        w_tpke_confidence: float = 0.15,
        w_recency: float = 0.10,
        w_root_cause_contribution: float = 0.10,
    ):
        self.w1 = w_query_similarity
        self.w2 = w_node_centrality
        self.w3 = w_business_importance
        self.w4 = w_prediction_confidence
        self.w5 = w_tpke_confidence
        self.w6 = w_recency
        self.w7 = w_root_cause_contribution

    def rank_context(
        self,
        raw_items: list[dict[str, Any]],
        user_query: str = "",
        top_k: int = 10,
        reference_time: datetime | None = None,
    ) -> list[RankedContextItem]:
        """Rank raw retrieved graph nodes and return Top-K with complete factor scores."""
        if not raw_items:
            return []

        ref = reference_time or datetime.now(timezone.utc)
        ranked: list[RankedContextItem] = []
        query_words = set(re.findall(r'\w+', user_query.lower())) if user_query else set()

        for item in raw_items:
            item_type = item.get("item_type", "node")
            props = item.get("properties", {}) or item

            # Factor 1: Query Similarity (0.0 to 1.0)
            title = str(props.get("name") or props.get("node_id") or props.get("supplier_name") or props.get("category_name") or "Graph Node")
            label = str(props.get("label", item.get("label", "Node")))
            sim_score = 0.5
            if query_words:
                node_text = (title + " " + label + " " + str(props)).lower()
                matches = sum(1 for w in query_words if w in node_text)
                sim_score = min(1.0, 0.3 + (matches / max(len(query_words), 1)) * 0.7)

            # Factor 2: Node Centrality (0.1 to 1.0)
            centrality = float(props.get("centrality", 0.5) or props.get("degree", 5) / 50.0)
            centrality = min(max(centrality, 0.1), 1.0)

            # Factor 3: Business Importance based on entity label (0.5 to 1.0)
            label_map = {"Supplier": 0.95, "Product": 0.90, "Warehouse": 0.85, "Shipment": 0.80}
            biz_importance = label_map.get(label, 0.70)

            # Factor 4: Prediction Confidence (0.1 to 1.0)
            pred_conf = float(props.get("prediction_confidence", 0.85) or props.get("confidence", 0.85))
            pred_conf = min(max(pred_conf, 0.1), 1.0)

            # Factor 5: TPKE Confidence (0.0 to 1.0)
            tpke_conf = float(props.get("tpke_confidence", 0.80) or props.get("weight", 0.80))
            tpke_conf = min(max(tpke_conf, 0.0), 1.0)

            # Factor 6: Recency (0.1 to 1.0)
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

            # Factor 7: Root Cause Contribution (0.1 to 1.0)
            rca_contribution = float(props.get("rca_contribution", 0.68) or props.get("contribution_score", 0.68))
            rca_contribution = min(max(rca_contribution, 0.1), 1.0)

            # 7-Factor Composite Scoring Formula
            total_score = (
                self.w1 * sim_score
                + self.w2 * centrality
                + self.w3 * biz_importance
                + self.w4 * pred_conf
                + self.w5 * tpke_conf
                + self.w6 * recency
                + self.w7 * rca_contribution
            )
            total_score = round(min(max(total_score, 0.0), 1.0), 4)

            factors = FactorScores(
                query_similarity=sim_score,
                node_centrality=centrality,
                business_importance=biz_importance,
                prediction_confidence=pred_conf,
                tpke_confidence=tpke_conf,
                recency=recency,
                root_cause_contribution=rca_contribution,
            )

            risk_val = float(props.get("risk_score", 0.5) or props.get("inventory_risk", 0.5))

            ranked.append(RankedContextItem(
                item_id=str(item.get("item_id") or props.get("node_id") or title),
                item_type=item_type,
                title=title,
                total_score=total_score,
                confidence=round(tpke_conf, 4),
                recency_score=round(recency, 4),
                risk_importance=round(risk_val, 4),
                factor_scores=factors,
                details=props,
            ))

        # Sort by composite score descending
        ranked.sort(key=lambda x: x.total_score, reverse=True)
        return ranked[:top_k]

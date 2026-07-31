"""
AMASCI Enhanced GraphRAG Response
=====================================
Enriches any GraphRAG query result with structured retrieval metadata.

Every response includes:
  - retrieved_entities   list of node IDs and labels actually retrieved
  - relationship_path    the primary traversal path as a readable string
  - evidence             grounded evidence items (node IDs + scores)
  - retrieval_confidence [0,1] score based on result count and risk coverage
  - top_retrieved_nodes  top 5 nodes ranked by risk score
  - cypher_summary       Cypher query used + execution stats
  - answer               grounded answer string (never generic)

Usage
-----
    from app.graphrag.enhanced_response import EnhancedResponseBuilder

    builder = EnhancedResponseBuilder()
    enhanced = builder.build(
        query_result=query_engine_result,
        chain_result=langchain_result,
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RetrievedEntity:
    node_id: str
    label: str
    risk_score: float = 0.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "risk_score": round(self.risk_score, 4),
        }


@dataclass
class EnhancedGraphRAGResponse:
    query: str
    answer: str
    retrieved_entities: list[RetrievedEntity]
    relationship_path: str
    evidence: list[str]
    retrieval_confidence: float
    top_retrieved_nodes: list[dict[str, Any]]
    cypher_summary: dict[str, Any]
    risks: Any
    recommendations: list[str]
    intent: str
    result_count: int
    duration_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "retrieved_entities": [e.to_dict() for e in self.retrieved_entities],
            "relationship_path": self.relationship_path,
            "evidence": self.evidence,
            "retrieval_confidence": round(self.retrieval_confidence, 4),
            "top_retrieved_nodes": self.top_retrieved_nodes,
            "cypher_summary": self.cypher_summary,
            "risks": self.risks,
            "recommendations": self.recommendations,
            "intent": self.intent,
            "result_count": self.result_count,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }


class EnhancedResponseBuilder:
    """
    Builds an EnhancedGraphRAGResponse from raw query engine and chain results.

    Inputs:
      query_result  — output of QueryEngine.execute_natural_language()
      chain_result  — output of GraphRAGChain.build_query_chain()
    """

    def build(
        self,
        query_result: dict[str, Any],
        chain_result: dict[str, Any],
    ) -> EnhancedGraphRAGResponse:
        """
        Merge query engine result and LangChain result into a rich response.
        """
        query = query_result.get("query", chain_result.get("query", ""))
        raw_results: list[dict[str, Any]] = query_result.get("results", [])
        intent = query_result.get("intent", "general")
        cypher = query_result.get("cypher", "")
        duration_ms = query_result.get("duration_ms", 0.0)
        result_count = query_result.get("result_count", len(raw_results))

        # Extract entities from raw results
        retrieved_entities = self._extract_entities(raw_results)

        # Build relationship path string
        relationship_path = self._build_path_string(raw_results, query_result)

        # Top nodes ranked by risk
        top_nodes = self._rank_top_nodes(retrieved_entities)

        # Retrieval confidence
        retrieval_confidence = self._compute_retrieval_confidence(
            result_count, retrieved_entities, intent
        )

        # Evidence from chain result
        evidence = self._extract_evidence(chain_result, retrieved_entities)

        # Answer — prefer chain result, never use generic fallback
        answer = self._extract_answer(chain_result, retrieved_entities, result_count, query)

        # Cypher summary
        cypher_summary = {
            "cypher": cypher,
            "parameters": query_result.get("parameters", {}),
            "result_count": result_count,
            "intent": intent,
            "resolved_entities": query_result.get("resolved_entities", []),
            "execution_ms": round(duration_ms, 2),
        }

        return EnhancedGraphRAGResponse(
            query=query,
            answer=answer,
            retrieved_entities=retrieved_entities,
            relationship_path=relationship_path,
            evidence=evidence,
            retrieval_confidence=retrieval_confidence,
            top_retrieved_nodes=top_nodes,
            cypher_summary=cypher_summary,
            risks=chain_result.get("risks", ""),
            recommendations=chain_result.get("recommendations", []),
            intent=intent,
            result_count=result_count,
            duration_ms=duration_ms,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_entities(self, raw_results: list[dict[str, Any]]) -> list[RetrievedEntity]:
        """Extract RetrievedEntity objects from raw Neo4j records."""
        entities: list[RetrievedEntity] = []
        seen: set[str] = set()

        for record in raw_results:
            # Records may have "node", "entity", or be flat
            node = record.get("node") or record.get("entity") or record
            node_id = (
                node.get("node_id") or node.get("id") or
                record.get("source_id") or record.get("entity_id") or ""
            )
            if not node_id or node_id in seen:
                continue
            seen.add(str(node_id))

            label = (
                node.get("_label") or node.get("label") or
                record.get("target_label") or "Unknown"
            )
            risk = float(
                node.get("risk_score") or node.get("late_delivery_rate") or
                node.get("warehouse_risk") or node.get("forecast_risk") or
                record.get("risk") or 0.0
            )
            entities.append(RetrievedEntity(
                node_id=str(node_id),
                label=str(label),
                risk_score=risk,
                properties={k: v for k, v in node.items() if not k.startswith("_")},
            ))

        return entities

    def _build_path_string(
        self,
        raw_results: list[dict[str, Any]],
        query_result: dict[str, Any],
    ) -> str:
        """Build a human-readable path string from path results or relationships."""
        # Check for explicit path_nodes
        for record in raw_results:
            path_nodes = record.get("path_nodes")
            if path_nodes:
                return " → ".join(
                    f"{n.get('label', '?')}:{n.get('node_id', '?')}"
                    for n in path_nodes
                )

        # Build from source/target pairs
        pairs = []
        for record in raw_results[:5]:
            src = record.get("source_id") or record.get("source")
            tgt = record.get("target_id") or record.get("target")
            rel = record.get("rel_type") or record.get("relationship", "→")
            if src and tgt:
                pairs.append(f"{src} -[{rel}]→ {tgt}")

        if pairs:
            return " | ".join(pairs[:3])

        # Fallback: entity chain from resolved entities
        entities = query_result.get("resolved_entities", [])
        if entities:
            return " → ".join(entities)

        return "No explicit path retrieved."

    def _rank_top_nodes(
        self, entities: list[RetrievedEntity], top_n: int = 5
    ) -> list[dict[str, Any]]:
        """Return top N nodes ranked by risk score."""
        sorted_entities = sorted(entities, key=lambda e: e.risk_score, reverse=True)
        return [e.to_dict() for e in sorted_entities[:top_n]]

    def _compute_retrieval_confidence(
        self,
        result_count: int,
        entities: list[RetrievedEntity],
        intent: str,
    ) -> float:
        """
        Compute retrieval confidence based on:
          - result count (more results = higher base confidence)
          - proportion of entities with non-zero risk scores
          - intent match quality
        """
        if result_count == 0:
            return 0.0

        # Base: log-scaled result count confidence
        import math
        base = min(1.0, math.log1p(result_count) / math.log1p(50))

        # Risk coverage bonus
        if entities:
            risk_coverage = sum(1 for e in entities if e.risk_score > 0) / len(entities)
        else:
            risk_coverage = 0.0

        # Intent bonus: path and risk queries are more precise
        intent_bonus = 0.1 if intent in ("risk", "path") else 0.0

        confidence = base * 0.6 + risk_coverage * 0.3 + intent_bonus
        return round(min(1.0, confidence), 4)

    def _extract_evidence(
        self,
        chain_result: dict[str, Any],
        entities: list[RetrievedEntity],
    ) -> list[str]:
        """Extract evidence list, preferring chain result, falling back to entity IDs."""
        chain_evidence = chain_result.get("evidence", [])
        if isinstance(chain_evidence, list) and chain_evidence:
            return [str(e) for e in chain_evidence[:8]]
        if isinstance(chain_evidence, str) and chain_evidence:
            return [chain_evidence]

        # Fallback: build from retrieved entities
        evidence = []
        for e in entities[:8]:
            if e.risk_score > 0:
                evidence.append(f"{e.node_id} ({e.label}): risk={e.risk_score:.3f}")
            else:
                evidence.append(f"{e.node_id} ({e.label})")
        return evidence

    def _extract_answer(
        self,
        chain_result: dict[str, Any],
        entities: list[RetrievedEntity],
        result_count: int,
        query: str,
    ) -> str:
        """Extract answer, ensuring it is never generic."""
        answer = chain_result.get("answer", "")
        if answer and len(str(answer)) > 20:
            return str(answer)

        # Build grounded fallback from retrieved entities
        if result_count == 0:
            return (
                f"No graph records matched the query '{query}'. "
                "Ensure the knowledge graph is built and Neo4j is reachable."
            )

        high_risk = [e for e in entities if e.risk_score >= 0.5]
        if high_risk:
            top = high_risk[0]
            return (
                f"Retrieved {result_count} records. "
                f"Highest risk entity: {top.node_id} ({top.label}) "
                f"with risk score {top.risk_score:.3f}. "
                f"{len(high_risk)} entities exceed the 0.5 risk threshold."
            )

        labels = list({e.label for e in entities})
        return (
            f"Retrieved {result_count} records across "
            f"{', '.join(labels[:3]) if labels else 'unknown'} nodes. "
            "No entities exceed the high-risk threshold."
        )

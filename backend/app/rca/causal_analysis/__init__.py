"""
AMASCI RCA Causal Analysis
=============================
Causal chain construction and multi-path causal reasoning.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.rca.utils import (
    PerformanceTimer, compute_risk_label, extract_node_risk,
    MAX_CAUSAL_CHAIN_LENGTH, RISK_PROPAGATION_DECAY,
)

logger = logging.getLogger(__name__)


@dataclass
class CausalEvent:
    """A single event in a causal chain."""
    node_id: str
    label: str
    event_description: str
    risk_score: float = 0.0
    risk_level: str = "low"
    position: int = 0
    relationship_to_next: str = ""
    confidence: float = 0.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "event_description": self.event_description,
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level,
            "position": self.position,
            "relationship_to_next": self.relationship_to_next,
            "confidence": round(self.confidence, 4),
        }


@dataclass
class CausalChain:
    """An ordered sequence of causal events."""
    chain_id: str
    events: list[CausalEvent] = field(default_factory=list)
    total_confidence: float = 0.0
    chain_length: int = 0
    root_cause_id: str = ""
    final_effect_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "events": [e.to_dict() for e in self.events],
            "total_confidence": round(self.total_confidence, 4),
            "chain_length": self.chain_length,
            "root_cause_id": self.root_cause_id,
            "final_effect_id": self.final_effect_id,
        }


@dataclass
class CausalAnalysisResult:
    """Complete causal analysis result."""
    target_id: str
    rca_type: str
    primary_chain: CausalChain | None = None
    alternative_chains: list[CausalChain] = field(default_factory=list)
    root_causes: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "rca_type": self.rca_type,
            "primary_chain": self.primary_chain.to_dict() if self.primary_chain else None,
            "alternative_chains": [c.to_dict() for c in self.alternative_chains],
            "root_causes": self.root_causes,
            "total_chains": 1 + len(self.alternative_chains) if self.primary_chain else 0,
            "duration_ms": round(self.duration_ms, 2),
        }


# Event description templates per label
EVENT_TEMPLATES = {
    "Supplier": "Supplier '{name}' experienced disruption (risk: {risk:.0%})",
    "Product": "Product category '{name}' demand anomaly (volatility: {risk:.0%})",
    "Warehouse": "Warehouse '{name}' capacity stress (stress: {risk:.0%})",
    "Shipment": "Shipment mode '{name}' delay (delay rate: {risk:.0%})",
    "Customer": "Customer segment '{name}' impact (orders affected)",
    "Order": "Order '{name}' delivery risk elevated (risk: {risk:.0%})",
    "CalendarEvent": "Calendar event '{name}' influence detected",
}


class CausalAnalysisEngine:
    """
    Constructs causal chains from graph traversal results.

    Generates ordered sequences of events showing how disruptions propagate
    through the supply chain graph.
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def analyze_causality(
        self, target_id: str, target_label: str, rca_type: str, max_chains: int = 3
    ) -> CausalAnalysisResult:
        """Perform full causal analysis for a disruption."""
        with PerformanceTimer("analyze_causality") as timer:
            # Find causal paths leading to the target
            raw_chains = await self._find_causal_paths(target_id, target_label, max_chains)

            # Build structured causal chains
            chains: list[CausalChain] = []
            for i, raw_chain in enumerate(raw_chains):
                chain = self._build_causal_chain(
                    f"chain_{i}", raw_chain, target_id, rca_type
                )
                chains.append(chain)

            # Select primary chain (highest confidence)
            primary = max(chains, key=lambda c: c.total_confidence) if chains else None
            alternatives = [c for c in chains if c != primary]

            # Extract root causes
            root_causes = self._extract_root_causes(chains)

        return CausalAnalysisResult(
            target_id=target_id,
            rca_type=rca_type,
            primary_chain=primary,
            alternative_chains=alternatives,
            root_causes=root_causes,
            duration_ms=timer.duration_ms,
        )

    async def _find_causal_paths(
        self, target_id: str, target_label: str, max_chains: int
    ) -> list[list[dict[str, Any]]]:
        """Find causal paths from high-risk upstream nodes to target."""
        query = f"""
            MATCH (target:{target_label} {{node_id: $target_id}})
            MATCH path = (root)-[*1..{MAX_CAUSAL_CHAIN_LENGTH}]->(target)
            WHERE root <> target
              AND coalesce(root.risk_score, root.late_delivery_rate,
                           root.supplier_delay_rate, root.warehouse_risk, 0) > 0.2
            WITH path,
                 reduce(risk = 0.0, n IN nodes(path) |
                     risk + coalesce(n.risk_score, n.late_delivery_rate,
                                     n.warehouse_risk, n.supplier_delay_rate, 0.0)
                 ) AS path_risk,
                 length(path) AS hops
            ORDER BY path_risk DESC
            LIMIT $max_chains
            RETURN
                [n IN nodes(path) | {{
                    node_id: n.node_id,
                    label: labels(n)[0],
                    properties: n {{.*}}
                }}] AS chain_nodes,
                [r IN relationships(path) | {{
                    type: type(r),
                    strength: coalesce(r.relationship_strength, 0.5)
                }}] AS chain_edges,
                path_risk,
                hops
        """
        records = await self._conn.execute_query(
            query, {"target_id": target_id, "max_chains": max_chains}
        )

        chains = []
        for record in records:
            chain_data = []
            nodes = record["chain_nodes"]
            edges = record["chain_edges"]
            for i, node in enumerate(nodes):
                edge_type = edges[i]["type"] if i < len(edges) else ""
                edge_strength = edges[i]["strength"] if i < len(edges) else 0.5
                chain_data.append({
                    **node,
                    "edge_to_next": edge_type,
                    "edge_strength": edge_strength,
                })
            chains.append(chain_data)

        return chains

    def _build_causal_chain(
        self,
        chain_id: str,
        raw_nodes: list[dict[str, Any]],
        target_id: str,
        rca_type: str,
    ) -> CausalChain:
        """Build a structured CausalChain from raw path data."""
        events: list[CausalEvent] = []
        total_confidence = 0.0

        for i, node_data in enumerate(raw_nodes):
            props = node_data.get("properties", {})
            label = node_data.get("label", "Unknown")
            node_id = node_data.get("node_id", "")
            risk = extract_node_risk(props)

            # Generate event description
            name = self._get_display_name(label, props)
            template = EVENT_TEMPLATES.get(label, "{name} event (risk: {risk:.0%})")
            description = template.format(name=name, risk=risk)

            # Confidence decays with position (root cause = highest confidence)
            position_factor = RISK_PROPAGATION_DECAY ** i
            confidence = min(1.0, risk * position_factor + 0.2)
            total_confidence += confidence

            events.append(CausalEvent(
                node_id=node_id,
                label=label,
                event_description=description,
                risk_score=risk,
                risk_level=compute_risk_label(risk),
                position=i,
                relationship_to_next=node_data.get("edge_to_next", ""),
                confidence=confidence,
                properties=props,
            ))

        avg_confidence = total_confidence / len(events) if events else 0.0

        return CausalChain(
            chain_id=chain_id,
            events=events,
            total_confidence=avg_confidence,
            chain_length=len(events),
            root_cause_id=events[0].node_id if events else "",
            final_effect_id=target_id,
        )

    def _extract_root_causes(self, chains: list[CausalChain]) -> list[dict[str, Any]]:
        """Extract unique root causes from all chains."""
        seen_ids: set[str] = set()
        root_causes: list[dict[str, Any]] = []

        for chain in chains:
            if chain.events:
                root = chain.events[0]
                if root.node_id not in seen_ids:
                    seen_ids.add(root.node_id)
                    root_causes.append({
                        "node_id": root.node_id,
                        "label": root.label,
                        "description": root.event_description,
                        "risk_score": root.risk_score,
                        "risk_level": root.risk_level,
                        "confidence": root.confidence,
                        "chain_id": chain.chain_id,
                    })

        root_causes.sort(key=lambda x: x["confidence"], reverse=True)
        return root_causes

    def _get_display_name(self, label: str, properties: dict[str, Any]) -> str:
        """Get display name for a node based on its label."""
        name_fields = {
            "Supplier": "supplier_name",
            "Product": "category",
            "Warehouse": "city",
            "Shipment": "shipping_mode",
            "Customer": "customer_id",
            "Order": "order_id",
            "CalendarEvent": "event_name",
        }
        field_name = name_fields.get(label, "node_id")
        return str(properties.get(field_name, properties.get("node_id", "unknown")))

"""
AMASCI GraphRAG Subgraph Engine
=================================
Generate relevant subgraphs around supply chain entities with configurable hop count.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graphrag.memory import get_context_cache
from app.graphrag.utils import PerformanceTimer, compute_risk_label

logger = logging.getLogger(__name__)

SUPPORTED_LABELS = ("Supplier", "Product", "Warehouse", "Shipment", "Customer", "Order", "CalendarEvent")


@dataclass
class SubgraphResult:
    """Structured subgraph extraction result."""
    center_id: str
    center_label: str
    center_properties: dict[str, Any] = field(default_factory=dict)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    hops: int = 1
    risk_summary: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "center_id": self.center_id,
            "center_label": self.center_label,
            "center_properties": self.center_properties,
            "nodes": self.nodes,
            "edges": self.edges,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "hops": self.hops,
            "risk_summary": self.risk_summary,
            "duration_ms": round(self.duration_ms, 2),
        }


class SubgraphEngine:
    """
    Subgraph extraction engine for GraphRAG.

    Generates relevant subgraphs around:
    - Supplier, Product, Warehouse, Shipment, Order, Customer, CalendarEvent

    Supports configurable hop count (1-Hop, 2-Hop, 3-Hop).
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()
        self._cache = get_context_cache()

    async def extract_subgraph(
        self, node_id: str, label: str, hops: int = 2, include_risk: bool = True
    ) -> SubgraphResult:
        """Extract a subgraph around a specific entity."""
        hops = max(1, min(3, hops))  # Clamp to [1, 3]

        cache_key = f"sg:{label}:{node_id}:{hops}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        with PerformanceTimer(f"extract_subgraph({label}, hops={hops})") as timer:
            # Get center node
            center = await self._get_center_node(node_id, label)
            if not center:
                return SubgraphResult(center_id=node_id, center_label=label, hops=hops)

            # Get neighborhood nodes and edges
            nodes, edges = await self._expand_neighborhood(node_id, label, hops)

            # Compute risk summary
            risk_summary = self._compute_risk_summary(nodes) if include_risk else {}

        result = SubgraphResult(
            center_id=node_id,
            center_label=label,
            center_properties=center,
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
            hops=hops,
            risk_summary=risk_summary,
            duration_ms=timer.duration_ms,
        )

        self._cache.set(cache_key, result)
        return result

    async def extract_supplier_subgraph(self, supplier_id: str, hops: int = 2) -> SubgraphResult:
        """Extract subgraph centered on a supplier."""
        return await self.extract_subgraph(supplier_id, "Supplier", hops)

    async def extract_product_subgraph(self, product_id: str, hops: int = 2) -> SubgraphResult:
        """Extract subgraph centered on a product."""
        return await self.extract_subgraph(product_id, "Product", hops)

    async def extract_warehouse_subgraph(self, warehouse_id: str, hops: int = 2) -> SubgraphResult:
        """Extract subgraph centered on a warehouse."""
        return await self.extract_subgraph(warehouse_id, "Warehouse", hops)

    async def extract_shipment_subgraph(self, shipment_id: str, hops: int = 2) -> SubgraphResult:
        """Extract subgraph centered on a shipment."""
        return await self.extract_subgraph(shipment_id, "Shipment", hops)

    async def extract_order_subgraph(self, order_id: str, hops: int = 2) -> SubgraphResult:
        """Extract subgraph centered on an order."""
        return await self.extract_subgraph(order_id, "Order", hops)

    async def extract_customer_subgraph(self, customer_id: str, hops: int = 2) -> SubgraphResult:
        """Extract subgraph centered on a customer."""
        return await self.extract_subgraph(customer_id, "Customer", hops)

    async def extract_calendar_subgraph(self, event_id: str, hops: int = 2) -> SubgraphResult:
        """Extract subgraph centered on a calendar event."""
        return await self.extract_subgraph(event_id, "CalendarEvent", hops)

    async def _get_center_node(self, node_id: str, label: str) -> dict[str, Any] | None:
        """Fetch center node properties."""
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})
            RETURN n {{.*}} AS props
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        return records[0]["props"] if records else None

    async def _expand_neighborhood(
        self, node_id: str, label: str, hops: int
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Expand neighborhood and collect nodes + edges."""
        query = f"""
            MATCH (center:{label} {{node_id: $node_id}})
            OPTIONAL MATCH path = (center)-[*1..{hops}]-(neighbor)
            WHERE neighbor <> center
            WITH center, neighbor, relationships(path) AS rels
            WITH collect(DISTINCT {{
                node_id: neighbor.node_id,
                label: labels(neighbor)[0],
                props: neighbor {{.*}}
            }}) AS nodes,
            collect(DISTINCT {{
                source: startNode(rels[0]).node_id,
                target: endNode(rels[0]).node_id,
                type: type(rels[0]),
                props: rels[0] {{.*}}
            }}) AS edges
            RETURN nodes[0..200] AS nodes, edges[0..500] AS edges
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        if not records:
            return [], []

        nodes = records[0].get("nodes", [])
        edges = records[0].get("edges", [])

        # Filter out null entries
        nodes = [n for n in nodes if n.get("node_id") is not None]
        edges = [e for e in edges if e.get("source") is not None]

        return nodes, edges

    def _compute_risk_summary(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute aggregate risk metrics from subgraph nodes."""
        risk_scores: list[float] = []
        risk_by_label: dict[str, list[float]] = {}

        for node in nodes:
            props = node.get("props", node)
            label = node.get("label", "Unknown")
            risk = (
                props.get("risk_score")
                or props.get("late_delivery_rate")
                or props.get("warehouse_risk")
                or props.get("forecast_risk")
                or 0.0
            )
            if isinstance(risk, (int, float)) and risk > 0:
                risk_scores.append(float(risk))
                risk_by_label.setdefault(label, []).append(float(risk))

        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
        max_risk = max(risk_scores) if risk_scores else 0.0

        label_risks = {}
        for lbl, scores in risk_by_label.items():
            label_risks[lbl] = {
                "avg_risk": round(sum(scores) / len(scores), 4),
                "max_risk": round(max(scores), 4),
                "count": len(scores),
            }

        return {
            "avg_risk": round(avg_risk, 4),
            "max_risk": round(max_risk, 4),
            "risk_level": compute_risk_label(avg_risk),
            "risk_node_count": len(risk_scores),
            "risk_by_label": label_risks,
        }

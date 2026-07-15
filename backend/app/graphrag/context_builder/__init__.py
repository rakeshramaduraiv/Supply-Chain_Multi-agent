"""
AMASCI GraphRAG Context Builder
==================================
Generates structured JSON context from graph data for downstream intelligence modules.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graphrag.retrieval import RetrievalEngine
from app.graphrag.subgraph import SubgraphEngine, SubgraphResult
from app.graphrag.dependency_analysis import DependencyAnalyzer
from app.graphrag.utils import PerformanceTimer, compute_risk_label, utc_now_iso
from app.graph.connection import Neo4jConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


@dataclass
class StructuredContext:
    """Structured graph context output."""
    context_type: str
    entity_id: str
    entity_label: str
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=utc_now_iso)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_type": self.context_type,
            "entity_id": self.entity_id,
            "entity_label": self.entity_label,
            "context": self.context,
            "metadata": self.metadata,
            "generated_at": self.generated_at,
            "duration_ms": round(self.duration_ms, 2),
        }


class ContextBuilder:
    """
    Builds structured JSON context from graph knowledge.

    Context types:
    - Supplier context (risk, reliability, products, warehouses)
    - Product context (demand, inventory, suppliers)
    - Warehouse context (stock, stress, shipments)
    - Shipment context (performance, delays, routes)
    - Forecast context (demand signals, seasonal patterns)
    - Risk context (risk propagation, critical dependencies)
    - Root cause context (late delivery, demand spike, supplier failure)
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        conn = connection or get_connection_manager()
        self._retrieval = RetrievalEngine(conn)
        self._subgraph = SubgraphEngine(conn)
        self._dependency = DependencyAnalyzer(conn)
        self._conn = conn

    async def build_supplier_context(self, supplier_id: str) -> StructuredContext:
        """Build comprehensive supplier context."""
        with PerformanceTimer("build_supplier_context") as timer:
            entity = await self._retrieval.retrieve_entity(supplier_id, "Supplier")
            if not entity:
                return StructuredContext(
                    context_type="supplier", entity_id=supplier_id, entity_label="Supplier"
                )

            relationships = await self._retrieval.retrieve_relationships(supplier_id, "Supplier")
            risk_neighborhood = await self._retrieval.retrieve_risk_neighborhood(supplier_id)

            # Extract connected entities
            products = [r for r in relationships if r.get("connected_label") == "Product"]
            warehouses = [r for r in relationships if r.get("connected_label") == "Warehouse"]
            shipments = [r for r in relationships if r.get("connected_label") == "Shipment"]

            context = {
                "supplier_profile": {
                    "name": entity.get("supplier_name", ""),
                    "reliability_score": entity.get("supplier_reliability_score", 0.0),
                    "delay_rate": entity.get("supplier_delay_rate", 0.0),
                    "total_orders": entity.get("total_orders", 0),
                    "risk_score": entity.get("risk_score", 0.0),
                    "risk_level": compute_risk_label(entity.get("risk_score", 0.0)),
                    "shipping_efficiency": entity.get("shipping_efficiency_score", 0.0),
                },
                "connected_products": [
                    {
                        "node_id": p.get("connected_id"),
                        "properties": p.get("connected_props", {}),
                    }
                    for p in products[:20]
                ],
                "connected_warehouses": [
                    {
                        "node_id": w.get("connected_id"),
                        "properties": w.get("connected_props", {}),
                    }
                    for w in warehouses[:10]
                ],
                "shipment_performance": [
                    {
                        "node_id": s.get("connected_id"),
                        "properties": s.get("connected_props", {}),
                    }
                    for s in shipments[:10]
                ],
                "risk_neighborhood": risk_neighborhood,
            }

        return StructuredContext(
            context_type="supplier",
            entity_id=supplier_id,
            entity_label="Supplier",
            context=context,
            metadata={"relationship_count": len(relationships)},
            duration_ms=timer.duration_ms,
        )

    async def build_product_context(self, product_id: str) -> StructuredContext:
        """Build comprehensive product context."""
        with PerformanceTimer("build_product_context") as timer:
            entity = await self._retrieval.retrieve_entity(product_id, "Product")
            if not entity:
                return StructuredContext(
                    context_type="product", entity_id=product_id, entity_label="Product"
                )

            relationships = await self._retrieval.retrieve_relationships(product_id, "Product")

            suppliers = [r for r in relationships if r.get("connected_label") == "Supplier"]
            warehouses = [r for r in relationships if r.get("connected_label") == "Warehouse"]
            orders = [r for r in relationships if r.get("connected_label") == "Order"]

            context = {
                "product_profile": {
                    "category": entity.get("category", ""),
                    "demand_volatility": entity.get("demand_volatility", 0.0),
                    "demand_trend": entity.get("demand_trend", 0.0),
                    "rolling_7d_demand": entity.get("rolling_7d_demand", 0.0),
                    "rolling_30d_demand": entity.get("rolling_30d_demand", 0.0),
                    "inventory_stress": entity.get("inventory_stress", 0.0),
                    "forecast_risk": entity.get("forecast_risk", 0.0),
                    "risk_level": compute_risk_label(entity.get("forecast_risk", 0.0)),
                },
                "suppliers": [
                    {"node_id": s.get("connected_id"), "properties": s.get("connected_props", {})}
                    for s in suppliers[:10]
                ],
                "warehouses": [
                    {"node_id": w.get("connected_id"), "properties": w.get("connected_props", {})}
                    for w in warehouses[:10]
                ],
                "recent_orders": [
                    {"node_id": o.get("connected_id"), "properties": o.get("connected_props", {})}
                    for o in orders[:20]
                ],
            }

        return StructuredContext(
            context_type="product",
            entity_id=product_id,
            entity_label="Product",
            context=context,
            metadata={"relationship_count": len(relationships)},
            duration_ms=timer.duration_ms,
        )

    async def build_warehouse_context(self, warehouse_id: str) -> StructuredContext:
        """Build comprehensive warehouse context."""
        with PerformanceTimer("build_warehouse_context") as timer:
            entity = await self._retrieval.retrieve_entity(warehouse_id, "Warehouse")
            if not entity:
                return StructuredContext(
                    context_type="warehouse", entity_id=warehouse_id, entity_label="Warehouse"
                )

            relationships = await self._retrieval.retrieve_relationships(warehouse_id, "Warehouse")

            products = [r for r in relationships if r.get("connected_label") == "Product"]
            shipments = [r for r in relationships if r.get("connected_label") == "Shipment"]

            context = {
                "warehouse_profile": {
                    "city": entity.get("city", ""),
                    "region": entity.get("region", ""),
                    "stock_coverage_ratio": entity.get("stock_coverage_ratio", 0.0),
                    "inventory_stress_index": entity.get("inventory_stress_index", 0.0),
                    "days_until_reorder": entity.get("days_until_reorder", 0.0),
                    "warehouse_risk": entity.get("warehouse_risk", 0.0),
                    "risk_level": compute_risk_label(entity.get("warehouse_risk", 0.0)),
                },
                "stored_products": [
                    {"node_id": p.get("connected_id"), "properties": p.get("connected_props", {})}
                    for p in products[:20]
                ],
                "shipment_routes": [
                    {"node_id": s.get("connected_id"), "properties": s.get("connected_props", {})}
                    for s in shipments[:10]
                ],
                "inventory_status": {
                    "total_products": len(products),
                    "total_shipments": len(shipments),
                },
            }

        return StructuredContext(
            context_type="warehouse",
            entity_id=warehouse_id,
            entity_label="Warehouse",
            context=context,
            metadata={"relationship_count": len(relationships)},
            duration_ms=timer.duration_ms,
        )

    async def build_shipment_context(self, shipment_id: str) -> StructuredContext:
        """Build comprehensive shipment context."""
        with PerformanceTimer("build_shipment_context") as timer:
            entity = await self._retrieval.retrieve_entity(shipment_id, "Shipment")
            if not entity:
                return StructuredContext(
                    context_type="shipment", entity_id=shipment_id, entity_label="Shipment"
                )

            relationships = await self._retrieval.retrieve_relationships(shipment_id, "Shipment")

            context = {
                "shipment_profile": {
                    "shipping_mode": entity.get("shipping_mode", ""),
                    "scheduled_days": entity.get("scheduled_days", 0.0),
                    "actual_days": entity.get("actual_days", 0.0),
                    "shipping_delay": entity.get("shipping_delay", 0.0),
                    "efficiency_score": entity.get("shipping_efficiency_score", 0.0),
                    "late_delivery_rate": entity.get("late_delivery_rate", 0.0),
                    "risk_level": compute_risk_label(entity.get("late_delivery_rate", 0.0)),
                },
                "connected_entities": [
                    {
                        "node_id": r.get("connected_id"),
                        "label": r.get("connected_label"),
                        "rel_type": r.get("rel_type"),
                    }
                    for r in relationships[:20]
                ],
            }

        return StructuredContext(
            context_type="shipment",
            entity_id=shipment_id,
            entity_label="Shipment",
            context=context,
            metadata={"relationship_count": len(relationships)},
            duration_ms=timer.duration_ms,
        )

    async def build_forecast_context(self, entity_id: str, entity_label: str) -> StructuredContext:
        """Build graph-aware forecast context for demand/inventory/supplier/logistics intelligence."""
        with PerformanceTimer("build_forecast_context") as timer:
            entity = await self._retrieval.retrieve_entity(entity_id, entity_label)
            if not entity:
                return StructuredContext(
                    context_type="forecast", entity_id=entity_id, entity_label=entity_label
                )

            subgraph = await self._subgraph.extract_subgraph(entity_id, entity_label, hops=2)
            dependencies = await self._dependency.analyze_dependencies(entity_id, entity_label)

            # Extract calendar events from neighborhood
            calendar_events = await self._retrieval.retrieve_neighborhood(
                entity_id, hops=2, label_filter="CalendarEvent"
            )

            context = {
                "entity_profile": entity,
                "demand_signals": {
                    "rolling_7d": entity.get("rolling_7d_demand", 0.0),
                    "rolling_30d": entity.get("rolling_30d_demand", 0.0),
                    "volatility": entity.get("demand_volatility", 0.0),
                    "trend": entity.get("demand_trend", 0.0),
                },
                "supply_chain_context": {
                    "upstream_count": len(dependencies.ancestors),
                    "downstream_count": len(dependencies.descendants),
                    "critical_dependencies": len(dependencies.critical_dependencies),
                    "impact_score": dependencies.impact_score,
                },
                "risk_context": subgraph.risk_summary,
                "calendar_events": [
                    {
                        "event_name": e.get("event_name", ""),
                        "event_type": e.get("event_type", ""),
                        "is_holiday": e.get("is_holiday", False),
                    }
                    for e in calendar_events[:10]
                ],
                "graph_features": {
                    "neighborhood_size": subgraph.node_count,
                    "edge_density": subgraph.edge_count / max(subgraph.node_count, 1),
                    "dependency_depth": dependencies.dependency_depth,
                },
            }

        return StructuredContext(
            context_type="forecast",
            entity_id=entity_id,
            entity_label=entity_label,
            context=context,
            metadata={"subgraph_nodes": subgraph.node_count},
            duration_ms=timer.duration_ms,
        )

    async def build_risk_context(self, entity_id: str, entity_label: str) -> StructuredContext:
        """Build risk reasoning context."""
        with PerformanceTimer("build_risk_context") as timer:
            entity = await self._retrieval.retrieve_entity(entity_id, entity_label)
            if not entity:
                return StructuredContext(
                    context_type="risk", entity_id=entity_id, entity_label=entity_label
                )

            risk_neighborhood = await self._retrieval.retrieve_risk_neighborhood(entity_id)
            impact = await self._dependency.propagate_impact(entity_id, entity_label)
            critical_deps = await self._dependency.detect_critical_dependencies(entity_id, entity_label)

            context = {
                "entity_risk": {
                    "risk_score": entity.get("risk_score", entity.get("late_delivery_rate", 0.0)),
                    "risk_level": compute_risk_label(
                        entity.get("risk_score", entity.get("late_delivery_rate", 0.0))
                    ),
                },
                "risk_neighborhood": risk_neighborhood,
                "impact_propagation": impact.to_dict(),
                "critical_dependencies": critical_deps,
                "risk_factors": self._extract_risk_factors(entity),
            }

        return StructuredContext(
            context_type="risk",
            entity_id=entity_id,
            entity_label=entity_label,
            context=context,
            metadata={"impacted_nodes": len(impact.impacted_nodes)},
            duration_ms=timer.duration_ms,
        )

    async def build_root_cause_context(
        self, entity_id: str, entity_label: str, issue_type: str
    ) -> StructuredContext:
        """
        Build context for root cause analysis support.

        Issue types: late_delivery, demand_spike, supplier_failure, inventory_stress, shipment_delay
        """
        with PerformanceTimer("build_root_cause_context") as timer:
            entity = await self._retrieval.retrieve_entity(entity_id, entity_label)
            if not entity:
                return StructuredContext(
                    context_type="root_cause", entity_id=entity_id, entity_label=entity_label
                )

            # Get upstream dependencies (potential causes)
            ancestors = await self._dependency.get_ancestors(entity_id, entity_label, max_depth=3)
            risk_neighborhood = await self._retrieval.retrieve_risk_neighborhood(
                entity_id, risk_threshold=0.3, hops=2
            )
            ranked_rels = await self._dependency.rank_relationships(entity_id, entity_label)

            # Issue-specific context
            issue_context = await self._build_issue_specific_context(
                entity_id, entity_label, issue_type
            )

            context = {
                "issue_type": issue_type,
                "entity_state": entity,
                "potential_causes": [
                    {
                        "node_id": a["node_id"],
                        "label": a["label"],
                        "distance": a["distance"],
                        "relationship_type": a["relationship_type"],
                        "risk_score": a["properties"].get(
                            "risk_score", a["properties"].get("late_delivery_rate", 0.0)
                        ),
                    }
                    for a in ancestors[:10]
                ],
                "risk_neighborhood": risk_neighborhood,
                "relationship_ranking": ranked_rels[:10],
                "issue_specific": issue_context,
            }

        return StructuredContext(
            context_type="root_cause",
            entity_id=entity_id,
            entity_label=entity_label,
            context=context,
            metadata={"issue_type": issue_type, "potential_causes": len(ancestors)},
            duration_ms=timer.duration_ms,
        )

    async def _build_issue_specific_context(
        self, entity_id: str, entity_label: str, issue_type: str
    ) -> dict[str, Any]:
        """Build context specific to the issue type."""
        if issue_type == "late_delivery":
            return await self._late_delivery_context(entity_id, entity_label)
        elif issue_type == "demand_spike":
            return await self._demand_spike_context(entity_id, entity_label)
        elif issue_type == "supplier_failure":
            return await self._supplier_failure_context(entity_id, entity_label)
        elif issue_type == "inventory_stress":
            return await self._inventory_stress_context(entity_id, entity_label)
        elif issue_type == "shipment_delay":
            return await self._shipment_delay_context(entity_id, entity_label)
        return {}

    async def _late_delivery_context(self, entity_id: str, entity_label: str) -> dict[str, Any]:
        """Context for late delivery root cause."""
        query = """
            MATCH (n {node_id: $node_id})-[:SHIPS_VIA|STORED_IN*1..2]-(logistics)
            WHERE labels(logistics)[0] IN ['Shipment', 'Warehouse']
            RETURN logistics {.*, _label: labels(logistics)[0]} AS node
            LIMIT 10
        """
        records = await self._conn.execute_query(query, {"node_id": entity_id})
        return {
            "logistics_chain": [r["node"] for r in records],
            "focus_areas": ["shipping_mode", "warehouse_capacity", "route_efficiency"],
        }

    async def _demand_spike_context(self, entity_id: str, entity_label: str) -> dict[str, Any]:
        """Context for demand spike root cause."""
        calendar = await self._retrieval.retrieve_neighborhood(
            entity_id, hops=2, label_filter="CalendarEvent"
        )
        return {
            "calendar_events": calendar[:5],
            "focus_areas": ["seasonal_patterns", "promotional_events", "market_trends"],
        }

    async def _supplier_failure_context(self, entity_id: str, entity_label: str) -> dict[str, Any]:
        """Context for supplier failure root cause."""
        query = """
            MATCH (n {node_id: $node_id})-[:SUPPLIES*1..2]-(supplier:Supplier)
            RETURN supplier {.*} AS node
            ORDER BY supplier.supplier_reliability_score ASC
            LIMIT 10
        """
        records = await self._conn.execute_query(query, {"node_id": entity_id})
        return {
            "related_suppliers": [r["node"] for r in records],
            "focus_areas": ["reliability_score", "delay_rate", "order_volume"],
        }

    async def _inventory_stress_context(self, entity_id: str, entity_label: str) -> dict[str, Any]:
        """Context for inventory stress root cause."""
        query = """
            MATCH (n {node_id: $node_id})-[:STORED_IN*1..2]-(warehouse:Warehouse)
            RETURN warehouse {.*} AS node
            ORDER BY warehouse.inventory_stress_index DESC
            LIMIT 10
        """
        records = await self._conn.execute_query(query, {"node_id": entity_id})
        return {
            "related_warehouses": [r["node"] for r in records],
            "focus_areas": ["stock_coverage", "reorder_timing", "demand_volatility"],
        }

    async def _shipment_delay_context(self, entity_id: str, entity_label: str) -> dict[str, Any]:
        """Context for shipment delay root cause."""
        query = """
            MATCH (n {node_id: $node_id})-[:SHIPS_VIA*1..2]-(shipment:Shipment)
            RETURN shipment {.*} AS node
            ORDER BY shipment.shipping_delay DESC
            LIMIT 10
        """
        records = await self._conn.execute_query(query, {"node_id": entity_id})
        return {
            "related_shipments": [r["node"] for r in records],
            "focus_areas": ["shipping_mode", "route_congestion", "carrier_performance"],
        }

    def _extract_risk_factors(self, entity: dict[str, Any]) -> list[dict[str, str]]:
        """Extract risk factors from entity properties."""
        factors = []
        risk_fields = {
            "risk_score": "Overall Risk",
            "late_delivery_rate": "Late Delivery",
            "supplier_delay_rate": "Supplier Delay",
            "warehouse_risk": "Warehouse Risk",
            "forecast_risk": "Forecast Risk",
            "inventory_stress": "Inventory Stress",
            "demand_volatility": "Demand Volatility",
        }
        for field_name, display_name in risk_fields.items():
            value = entity.get(field_name)
            if isinstance(value, (int, float)) and value > 0.25:
                factors.append({
                    "factor": display_name,
                    "value": round(float(value), 4),
                    "level": compute_risk_label(float(value)),
                })
        return sorted(factors, key=lambda x: x["value"], reverse=True)

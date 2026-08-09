"""
AMASCI Graph Builder
======================
Bulk graph construction with MERGE queries, batch processing, and transaction management.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager
from app.graph.nodes import (
    BaseNode,
    CalendarEventNode,
    CustomerNode,
    InventoryNode,
    OrderNode,
    ProductNode,
    RouteNode,
    ShipmentNode,
    SupplierNode,
    SupplierRouteNode,
    WarehouseNode,
)
from app.graph.relationships import BaseRelationship
from app.graph.utils import DEFAULT_BATCH_SIZE, chunk_list, utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of a graph build operation."""
    nodes_created: int = 0
    relationships_created: int = 0
    nodes_updated: int = 0
    relationships_updated: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    graph_version: str = ""
    build_timestamp: str = field(default_factory=utc_now_iso)
    dataset_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes_created": self.nodes_created,
            "relationships_created": self.relationships_created,
            "nodes_updated": self.nodes_updated,
            "relationships_updated": self.relationships_updated,
            "errors": self.errors,
            "duration_ms": round(self.duration_ms, 2),
            "graph_version": self.graph_version,
            "build_timestamp": self.build_timestamp,
            "dataset_version": self.dataset_version,
        }


# --- Cypher MERGE Templates ---

_NODE_MERGE_TEMPLATES = {
    "SupplierRoute": """
        UNWIND $batch AS props
        MERGE (n:SupplierRoute {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Route": """
        UNWIND $batch AS props
        MERGE (n:Route {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Inventory": """
        UNWIND $batch AS props
        MERGE (n:Inventory {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Supplier": """
        UNWIND $batch AS props
        MERGE (n:Supplier {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Product": """
        UNWIND $batch AS props
        MERGE (n:Product {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Warehouse": """
        UNWIND $batch AS props
        MERGE (n:Warehouse {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Shipment": """
        UNWIND $batch AS props
        MERGE (n:Shipment {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Customer": """
        UNWIND $batch AS props
        MERGE (n:Customer {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "Order": """
        UNWIND $batch AS props
        MERGE (n:Order {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
    "TemporalPeriod": """
        UNWIND $batch AS props
        MERGE (n:TemporalPeriod {node_id: props.node_id})
        SET n += props, n.updated_at = $now
        RETURN count(n) AS cnt
    """,
}

_REL_MERGE_TEMPLATE = """
    UNWIND $batch AS rel
    MATCH (a:{source_label} {{node_id: rel.source_id}})
    MATCH (b:{target_label} {{node_id: rel.target_id}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r.relationship_strength = rel.relationship_strength,
        r.frequency = rel.frequency,
        r.avg_delay = rel.avg_delay,
        r.confidence = rel.confidence,
        r.created_at = rel.created_at,
        r.updated_at = rel.updated_at
    RETURN count(r) AS cnt
"""


class GraphBuilder:
    """
    Builds the Knowledge Graph in Neo4j using batch MERGE operations.

    Features:
    - Bulk node creation with duplicate prevention (MERGE)
    - Bulk relationship creation
    - Batch processing for large datasets
    - Transaction management with rollback
    - Constraint and index creation
    """

    def __init__(self, connection: Neo4jConnectionManager):
        self._conn = connection
        self._batch_size = DEFAULT_BATCH_SIZE

    async def create_constraints(self) -> None:
        """Create uniqueness constraints and indexes for all node types."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SupplierRoute) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Route) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Inventory) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Supplier) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Product) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Warehouse) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Shipment) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Customer) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Order) REQUIRE n.node_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:TemporalPeriod) REQUIRE n.node_id IS UNIQUE",
        ]
        for cypher in constraints:
            try:
                await self._conn.execute_write(cypher)
            except Exception as e:
                logger.warning(f"Constraint creation skipped: {e}")

        logger.info("Graph constraints ensured")

    async def clear_graph(self) -> None:
        """Delete all nodes and relationships (full rebuild)."""
        await self._conn.execute_write("MATCH (n) DETACH DELETE n")
        logger.info("Graph cleared")

    async def build_nodes(self, nodes: list[BaseNode], label: str) -> int:
        """Bulk MERGE nodes of a given label."""
        if not nodes:
            return 0

        template = _NODE_MERGE_TEMPLATES.get(label)
        if not template:
            logger.error(f"No MERGE template for label: {label}")
            return 0

        total_created = 0
        batches = chunk_list([n.to_dict() for n in nodes], self._batch_size)
        now = utc_now_iso()

        for batch in batches:
            try:
                records = await self._conn.execute_write(template, {"batch": batch, "now": now})
                if records:
                    total_created += records[0].get("cnt", 0)
            except Exception as e:
                logger.error(f"Failed to create {label} batch: {e}")

        logger.info(f"Built {total_created} {label} nodes")
        return total_created

    async def build_relationships(self, relationships: list[BaseRelationship]) -> int:
        """Bulk MERGE relationships grouped by type."""
        if not relationships:
            return 0

        # Group by (rel_type, source_label, target_label)
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for rel in relationships:
            key = (rel.rel_type, rel.source_label, rel.target_label)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append({
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "relationship_strength": rel.relationship_strength,
                "frequency": rel.frequency,
                "avg_delay": rel.avg_delay,
                "confidence": rel.confidence,
                "created_at": rel.created_at,
                "updated_at": rel.updated_at,
            })

        total_created = 0
        for (rel_type, source_label, target_label), rel_batch in grouped.items():
            query = _REL_MERGE_TEMPLATE.format(
                source_label=source_label,
                target_label=target_label,
                rel_type=rel_type,
            )
            batches = chunk_list(rel_batch, self._batch_size)
            for batch in batches:
                try:
                    records = await self._conn.execute_write(query, {"batch": batch})
                    if records:
                        total_created += records[0].get("cnt", 0)
                except Exception as e:
                    logger.error(f"Failed to create {rel_type} batch: {e}")

        logger.info(f"Built {total_created} relationships")
        return total_created

    async def build_full_graph(
        self,
        suppliers: list[SupplierNode],
        products: list[ProductNode],
        warehouses: list[WarehouseNode],
        shipments: list[ShipmentNode],
        customers: list[CustomerNode],
        orders: list[OrderNode],
        calendar_events: list[CalendarEventNode],
        relationships: list[BaseRelationship],
        dataset_version: str = "",
        clear_existing: bool = False,
        supplier_routes: list[SupplierRouteNode] | None = None,
        routes: list[RouteNode] | None = None,
        inventories: list[InventoryNode] | None = None,
    ) -> BuildResult:
        """
        Build the complete Knowledge Graph.

        Steps:
        1. Create constraints
        2. Optionally clear existing graph
        3. MERGE all nodes by type
        4. MERGE all relationships
        5. Return build result with metrics
        """
        start = time.perf_counter()
        result = BuildResult(dataset_version=dataset_version)
        result.graph_version = f"v_{int(time.time())}"

        try:
            await self.create_constraints()

            if clear_existing:
                await self.clear_graph()

            # Fine-grained enrichment nodes first (enrichment Cypher depends on them)
            if supplier_routes:
                result.nodes_created += await self.build_nodes(supplier_routes, "SupplierRoute")
            if routes:
                result.nodes_created += await self.build_nodes(routes, "Route")
            if inventories:
                result.nodes_created += await self.build_nodes(inventories, "Inventory")

            # Coarse nodes (TPKE / RCA)
            result.nodes_created += await self.build_nodes(suppliers, "Supplier")
            result.nodes_created += await self.build_nodes(products, "Product")
            result.nodes_created += await self.build_nodes(warehouses, "Warehouse")
            result.nodes_created += await self.build_nodes(shipments, "Shipment")
            result.nodes_created += await self.build_nodes(customers, "Customer")
            result.nodes_created += await self.build_nodes(orders, "Order")
            result.nodes_created += await self.build_nodes(calendar_events, "TemporalPeriod")

            # Build relationships
            result.relationships_created = await self.build_relationships(relationships)

            # Build peer edges — must run AFTER all fine-grained nodes exist.
            # These cross-key edges are what make enrichment traversal
            # structurally different from a pandas groupby.
            peer_edges = await self.build_peer_edges()
            result.relationships_created += peer_edges

        except Exception as e:
            result.errors.append(str(e))
            logger.error(f"Graph build failed: {e}", exc_info=True)

        result.duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Graph build complete: {result.nodes_created} nodes, "
            f"{result.relationships_created} rels, {result.duration_ms:.1f}ms"
        )
        return result

    async def build_peer_edges(self) -> int:
        """
        Create cross-key peer edges on the training-slice nodes.
        These edges are what make enrichment structurally different from a groupby.

        :SIMILAR_TO   — SupplierRoute pairs sharing dept OR category (not both).
                        weight = 1 / (1 + |reliability_score_a - reliability_score_b|)
                        so closer peers get higher weight in the blend.

        :SHARES_LANE  — Route pairs sharing region but different shipping_mode.
                        weight = 1 / (1 + |avg_delay_a - avg_delay_b|)

        :SAME_CATEGORY — Inventory pairs sharing category but different region.
                        weight = 1 / (1 + |avg_inventory_stress_a - avg_inventory_stress_b|)
        """
        total = 0

        # :SIMILAR_TO on SupplierRoute — same dept, different category
        q_similar_dept = """
        MATCH (a:SupplierRoute), (b:SupplierRoute)
        WHERE a.dept = b.dept
          AND a.category <> b.category
          AND a.node_id < b.node_id
        WITH a, b,
             1.0 / (1.0 + abs(a.reliability_score - b.reliability_score)) AS w
        ORDER BY w DESC LIMIT 2000
        MERGE (a)-[r:SIMILAR_TO]-(b)
        SET r.weight = w, r.basis = 'dept'
        RETURN count(r) AS cnt
        """
        # :SIMILAR_TO on SupplierRoute — same category, different dept
        q_similar_cat = """
        MATCH (a:SupplierRoute), (b:SupplierRoute)
        WHERE a.category = b.category
          AND a.dept <> b.dept
          AND a.node_id < b.node_id
        WITH a, b,
             1.0 / (1.0 + abs(a.reliability_score - b.reliability_score)) AS w
        ORDER BY w DESC LIMIT 2000
        MERGE (a)-[r:SIMILAR_TO]-(b)
        SET r.weight = w, r.basis = 'category'
        RETURN count(r) AS cnt
        """
        # :SHARES_LANE on Route — same region, different shipping_mode
        q_shares_lane = """
        MATCH (a:Route), (b:Route)
        WHERE a.order_region = b.order_region
          AND a.shipping_mode <> b.shipping_mode
          AND a.node_id < b.node_id
        WITH a, b,
             1.0 / (1.0 + abs(a.avg_delay - b.avg_delay)) AS w
        ORDER BY w DESC LIMIT 2000
        MERGE (a)-[r:SHARES_LANE]-(b)
        SET r.weight = w
        RETURN count(r) AS cnt
        """
        # :SAME_CATEGORY on Inventory — same category, different region
        q_same_cat = """
        MATCH (a:Inventory), (b:Inventory)
        WHERE a.category = b.category
          AND a.region <> b.region
          AND a.node_id < b.node_id
        WITH a, b,
             1.0 / (1.0 + abs(a.avg_inventory_stress - b.avg_inventory_stress)) AS w
        ORDER BY w DESC LIMIT 2000
        MERGE (a)-[r:SAME_CATEGORY]-(b)
        SET r.weight = w
        RETURN count(r) AS cnt
        """

        for label, query in [
            ("SIMILAR_TO (dept)",    q_similar_dept),
            ("SIMILAR_TO (category)", q_similar_cat),
            ("SHARES_LANE",          q_shares_lane),
            ("SAME_CATEGORY",        q_same_cat),
        ]:
            try:
                records = await self._conn.execute_write(query)
                cnt = records[0].get("cnt", 0) if records else 0
                logger.info(f"build_peer_edges: {cnt} {label} edges created/updated")
                total += cnt
            except Exception as e:
                logger.error(f"build_peer_edges {label} failed: {e}")

        logger.info(f"build_peer_edges complete: {total} total peer edges")
        return total

    async def delete_nodes_by_label(self, label: str) -> int:
        """Delete all nodes of a specific label."""
        query = f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) AS cnt"
        records = await self._conn.execute_write(query)
        count = records[0]["cnt"] if records else 0
        logger.info(f"Deleted {count} {label} nodes")
        return count

    async def update_node_properties(
        self, label: str, node_id: str, properties: dict[str, Any]
    ) -> bool:
        """Update properties on a specific node."""
        set_parts = ", ".join(f"n.{k} = ${k}" for k in properties)
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})
            SET {set_parts}, n.updated_at = $now
            RETURN n.node_id AS nid
        """
        params = {"node_id": node_id, "now": utc_now_iso(), **properties}
        records = await self._conn.execute_write(query, params)
        return len(records) > 0

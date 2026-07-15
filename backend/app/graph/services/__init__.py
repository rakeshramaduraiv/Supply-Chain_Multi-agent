"""
AMASCI Graph Service
======================
Business logic orchestration for Knowledge Graph operations.
Integrates: Orchestrator, Versioning, Schema, Analytics, Repository.
"""

import logging
import time
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.analytics import GraphAnalytics, GraphStatistics
from app.graph.builder import BuildResult, GraphBuilder
from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graph.extractor import EntityExtractor
from app.graph.loader import BatchLoader, LoadResult
from app.graph.orchestrator import GraphOrchestrator, OrchestrationResult
from app.graph.repository import GraphRepository
from app.graph.schema import Neo4jSchemaManager
from app.graph.utils import utc_now_iso
from app.graph.validator import GraphValidator, ValidationResult
from app.graph.versioning import GraphVersionManager

logger = logging.getLogger(__name__)


class GraphService:
    """
    Orchestrates all Knowledge Graph operations.

    Provides:
    - Build graph from dataset (via Orchestrator)
    - Incremental update
    - Full rebuild
    - Validation
    - Export/Import
    - Statistics
    - Version management
    """

    def __init__(
        self,
        connection: Neo4jConnectionManager | None = None,
        session: AsyncSession | None = None,
    ):
        self._conn = connection or get_connection_manager()
        self._session = session
        self._extractor = EntityExtractor()
        self._builder = GraphBuilder(self._conn)
        self._repository = GraphRepository(self._conn)
        self._analytics = GraphAnalytics(self._conn)
        self._validator = GraphValidator(self._conn)
        self._schema = Neo4jSchemaManager(self._conn)

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD OPERATIONS (via Orchestrator)
    # ─────────────────────────────────────────────────────────────────────────

    async def build_graph(
        self,
        df: pd.DataFrame,
        dataset_version: str = "",
        clear_existing: bool = False,
        order_sample_size: int = 5000,
        dataset_id: str | None = None,
    ) -> BuildResult:
        """
        Build the complete Knowledge Graph from an engineered dataset.
        Uses the Orchestrator for production builds when session is available.
        Falls back to direct builder for sessionless operation.
        """
        if self._session:
            orchestrator = GraphOrchestrator(
                connection=self._conn,
                session=self._session,
                order_sample_size=order_sample_size,
            )
            orch_result = await orchestrator.build(
                df=df,
                dataset_id=dataset_id,
                clear_existing=clear_existing,
                built_by="system",
            )
            # Map to BuildResult for backward compatibility
            return BuildResult(
                nodes_created=orch_result.node_count,
                relationships_created=orch_result.relationship_count,
                errors=orch_result.errors,
                duration_ms=orch_result.duration_ms,
                graph_version=f"v{orch_result.version_number}",
                dataset_version=dataset_version,
            )

        # Fallback: direct builder (no versioning)
        return await self._build_direct(df, dataset_version, clear_existing, order_sample_size)

    async def update_graph(self, df: pd.DataFrame, dataset_version: str = "") -> BuildResult:
        """Incremental graph update (MERGE without clearing)."""
        return await self.build_graph(df, dataset_version=dataset_version, clear_existing=False)

    async def rebuild_graph(self, df: pd.DataFrame, dataset_version: str = "") -> BuildResult:
        """Full graph rebuild (clear + build)."""
        return await self.build_graph(df, dataset_version=dataset_version, clear_existing=True)

    # ─────────────────────────────────────────────────────────────────────────
    # SCHEMA
    # ─────────────────────────────────────────────────────────────────────────

    async def initialize_schema(self) -> dict[str, Any]:
        """Initialize all Neo4j constraints and indexes."""
        return await self._schema.initialize_schema()

    async def get_schema_info(self) -> dict[str, Any]:
        """Get current schema state."""
        return await self._schema.get_schema_info()

    # ─────────────────────────────────────────────────────────────────────────
    # VERSIONING
    # ─────────────────────────────────────────────────────────────────────────

    async def get_active_version(self) -> dict[str, Any] | None:
        """Get active graph version."""
        if not self._session:
            return await self._get_neo4j_version()
        mgr = GraphVersionManager(self._conn, self._session)
        return await mgr.get_active_version()

    async def list_versions(self, skip: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        """List all graph versions."""
        if not self._session:
            return []
        mgr = GraphVersionManager(self._conn, self._session)
        return await mgr.list_versions(skip=skip, limit=limit)

    async def rollback_version(self, target_version: int) -> dict[str, Any] | None:
        """Rollback to a previous graph version."""
        if not self._session:
            return None
        mgr = GraphVersionManager(self._conn, self._session)
        return await mgr.rollback(target_version)

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDATION & ANALYTICS
    # ─────────────────────────────────────────────────────────────────────────

    async def validate_graph(self) -> ValidationResult:
        """Run graph validation checks."""
        return await self._validator.validate()

    async def get_statistics(self) -> GraphStatistics:
        """Get graph statistics."""
        return await self._analytics.get_statistics()

    async def degree_centrality(self, label: str, top_n: int = 10) -> list[dict[str, Any]]:
        """Get degree centrality for a label."""
        return await self._analytics.degree_centrality(label, top_n)

    async def pagerank(self, label: str, top_n: int = 10) -> list[dict[str, Any]]:
        """Get PageRank for a label."""
        return await self._analytics.pagerank(label, top_n)

    async def shortest_path(self, source_id: str, target_id: str) -> list[dict[str, Any]]:
        """Find shortest path."""
        return await self._analytics.shortest_path(source_id, target_id)

    # ─────────────────────────────────────────────────────────────────────────
    # ENTITY OPERATIONS
    # ─────────────────────────────────────────────────────────────────────────

    async def get_entity(self, node_id: str) -> dict[str, Any] | None:
        """Fetch an entity with connections."""
        return await self._repository.fetch_entity(node_id)

    async def get_subgraph(self, node_id: str, max_hops: int = 2) -> dict[str, Any]:
        """Fetch subgraph around a node."""
        return await self._repository.fetch_subgraph(node_id, max_hops=max_hops)

    async def get_nodes(self, label: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Get nodes by label."""
        return await self._repository.get_nodes(label, limit=limit, offset=offset)

    async def get_relationships_for_node(self, label: str, node_id: str) -> list[dict[str, Any]]:
        """Get relationships for a node."""
        return await self._repository.get_relationships(label, node_id)

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORT / IMPORT
    # ─────────────────────────────────────────────────────────────────────────

    async def export_graph(self) -> dict[str, Any]:
        """Export graph as JSON structure."""
        export_data: dict[str, Any] = {"nodes": {}, "relationships": [], "metadata": {}}

        labels = ["Supplier", "Product", "Warehouse", "Shipment", "Customer", "Order", "CalendarEvent"]
        for label in labels:
            nodes = await self._repository.get_nodes(label, limit=10000)
            export_data["nodes"][label] = nodes

        records = await self._conn.execute_query("""
            MATCH (a)-[r]->(b)
            RETURN labels(a)[0] AS source_label, a.node_id AS source_id,
                   type(r) AS rel_type, r {.*} AS props,
                   labels(b)[0] AS target_label, b.node_id AS target_id
            LIMIT 50000
        """)
        export_data["relationships"] = records
        export_data["metadata"] = {"exported_at": utc_now_iso()}
        return export_data

    async def import_graph(self, data: dict[str, Any]) -> BuildResult:
        """Import graph from exported JSON structure."""
        start = time.perf_counter()
        result = BuildResult()

        await self._builder.create_constraints()

        nodes_data = data.get("nodes", {})
        for label, nodes in nodes_data.items():
            for node_props in nodes:
                if "node_id" in node_props:
                    await self._repository.create_node(label, node_props)
                    result.nodes_created += 1

        rels_data = data.get("relationships", [])
        for rel in rels_data:
            await self._repository.create_relationship(
                source_label=rel.get("source_label", ""),
                source_id=rel.get("source_id", ""),
                target_label=rel.get("target_label", ""),
                target_id=rel.get("target_id", ""),
                rel_type=rel.get("rel_type", ""),
                properties=rel.get("props", {}),
            )
            result.relationships_created += 1

        result.duration_ms = (time.perf_counter() - start) * 1000
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # PRIVATE
    # ─────────────────────────────────────────────────────────────────────────

    async def _build_direct(
        self,
        df: pd.DataFrame,
        dataset_version: str,
        clear_existing: bool,
        order_sample_size: int,
    ) -> BuildResult:
        """Direct build without orchestrator (no session/versioning)."""
        suppliers = self._extractor.extract_suppliers(df)
        products = self._extractor.extract_products(df)
        warehouses = self._extractor.extract_warehouses(df)
        shipments = self._extractor.extract_shipments(df)
        customers = self._extractor.extract_customers(df)
        orders = self._extractor.extract_orders(df, sample_size=order_sample_size)
        calendar_events = self._extractor.extract_calendar_events(df)

        relationships = self._extractor.extract_relationships(
            df, suppliers, products, warehouses, shipments, customers, orders, calendar_events
        )

        return await self._builder.build_full_graph(
            suppliers=suppliers,
            products=products,
            warehouses=warehouses,
            shipments=shipments,
            customers=customers,
            orders=orders,
            calendar_events=calendar_events,
            relationships=relationships,
            dataset_version=dataset_version,
            clear_existing=clear_existing,
        )

    async def _get_neo4j_version(self) -> dict[str, Any] | None:
        """Get version from Neo4j meta node (fallback when no session)."""
        records = await self._conn.execute_query(
            "MATCH (meta:_GraphMeta {key: 'active_version'}) RETURN meta {.*} AS meta"
        )
        return records[0]["meta"] if records else None

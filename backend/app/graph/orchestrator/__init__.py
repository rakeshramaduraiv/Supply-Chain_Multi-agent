"""
AMASCI Graph Orchestrator
============================
Production pipeline that coordinates:
1. Schema initialization (constraints + indexes)
2. Entity extraction from DataFrame
3. Batch loading into Neo4j
4. Version management (PostgreSQL + Neo4j meta)
5. Validation

This is the single entry point for building/rebuilding the Knowledge Graph.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graph.extractor import EntityExtractor
from app.graph.loader import BatchLoader, LoadResult
from app.graph.schema import Neo4jSchemaManager
from app.graph.validator import GraphValidator, ValidationResult
from app.graph.versioning import GraphVersionManager
from app.graph.utils import utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    """Complete result of a graph build orchestration."""
    version_id: str = ""
    version_number: int = 0
    node_count: int = 0
    relationship_count: int = 0
    nodes_by_label: dict[str, int] = field(default_factory=dict)
    relationships_by_type: dict[str, int] = field(default_factory=dict)
    schema_result: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    status: str = "pending"
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "node_count": self.node_count,
            "relationship_count": self.relationship_count,
            "nodes_by_label": self.nodes_by_label,
            "relationships_by_type": self.relationships_by_type,
            "schema_result": self.schema_result,
            "validation": self.validation,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "errors": self.errors,
        }


class GraphOrchestrator:
    """
    Production graph build orchestrator.

    Usage:
        orchestrator = GraphOrchestrator(connection, session)
        result = await orchestrator.build(df, dataset_id="abc123")
    """

    def __init__(
        self,
        connection: Neo4jConnectionManager | None = None,
        session: AsyncSession | None = None,
        batch_size: int = 500,
        order_sample_size: int = 5000,
        on_progress: Callable | None = None,
    ):
        self._conn = connection or get_connection_manager()
        self._session = session
        self._batch_size = batch_size
        self._order_sample_size = order_sample_size
        self._on_progress = on_progress

        self._schema = Neo4jSchemaManager(self._conn)
        self._extractor = EntityExtractor()
        self._validator = GraphValidator(self._conn)

    async def build(
        self,
        df: pd.DataFrame,
        dataset_id: str | None = None,
        clear_existing: bool = False,
        validate: bool = True,
        built_by: str = "system",
    ) -> OrchestrationResult:
        """
        Full graph build pipeline:
        1. Initialize schema (constraints + indexes)
        2. Optionally clear existing graph
        3. Start version record
        4. Extract entities from DataFrame
        5. Batch load nodes + relationships
        6. Complete version
        7. Validate (optional)
        """
        start = time.perf_counter()
        result = OrchestrationResult(status="building")

        try:
            # Step 1: Schema
            logger.info("Step 1/6: Initializing schema...")
            result.schema_result = await self._schema.initialize_schema()

            # Step 2: Clear if requested
            if clear_existing:
                logger.info("Step 2/6: Clearing existing graph...")
                await self._conn.execute_write("MATCH (n) WHERE NOT n:_GraphMeta DETACH DELETE n")
            else:
                logger.info("Step 2/6: Incremental mode (skip clear)")

            # Step 3: Start version
            version_info = None
            if self._session:
                logger.info("Step 3/6: Creating version record...")
                version_mgr = GraphVersionManager(self._conn, self._session)
                version_info = await version_mgr.start_version(
                    source_dataset_id=dataset_id,
                    built_by=built_by,
                )
                result.version_id = version_info["id"]
                result.version_number = version_info["version"]
            else:
                logger.info("Step 3/6: No session — skipping version persistence")

            # Step 4: Extract entities
            logger.info("Step 4/6: Extracting entities...")
            suppliers = self._extractor.extract_suppliers(df)
            products = self._extractor.extract_products(df)
            warehouses = self._extractor.extract_warehouses(df)
            shipments = self._extractor.extract_shipments(df)
            customers = self._extractor.extract_customers(df)
            orders = self._extractor.extract_orders(df, sample_size=self._order_sample_size)
            calendar_events = self._extractor.extract_calendar_events(df)

            relationships = self._extractor.extract_relationships(
                df, suppliers, products, warehouses, shipments, customers, orders, calendar_events
            )

            # Step 5: Batch load
            logger.info("Step 5/6: Batch loading into Neo4j...")
            loader = BatchLoader(
                self._conn,
                batch_size=self._batch_size,
                on_progress=self._on_progress,
            )

            node_groups = {
                "Supplier": suppliers,
                "Product": products,
                "Warehouse": warehouses,
                "Shipment": shipments,
                "Customer": customers,
                "Order": orders,
                "CalendarEvent": calendar_events,
            }

            load_result = await loader.load_all(node_groups, relationships)
            result.node_count = load_result.total_nodes
            result.relationship_count = load_result.total_relationships
            result.nodes_by_label = load_result.nodes_loaded
            result.relationships_by_type = load_result.relationships_loaded
            result.errors.extend(load_result.errors)

            # Step 6: Complete version
            result.duration_ms = (time.perf_counter() - start) * 1000
            if self._session and version_info:
                logger.info("Step 6/6: Completing version...")
                version_mgr = GraphVersionManager(self._conn, self._session)
                await version_mgr.complete_version(
                    version_id=result.version_id,
                    node_count=result.node_count,
                    relationship_count=result.relationship_count,
                    build_duration_ms=result.duration_ms,
                    metadata={
                        "nodes_by_label": result.nodes_by_label,
                        "relationships_by_type": result.relationships_by_type,
                        "dataset_rows": len(df),
                        "order_sample_size": self._order_sample_size,
                    },
                )
            else:
                logger.info("Step 6/6: Skipping version persistence")

            # Optional validation
            if validate:
                logger.info("Running post-build validation...")
                validation = await self._validator.validate()
                result.validation = validation.to_dict()

            result.status = "completed"
            logger.info(
                f"Graph orchestration complete: v{result.version_number}, "
                f"{result.node_count} nodes, {result.relationship_count} rels, "
                f"{result.duration_ms:.0f}ms"
            )

        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
            result.duration_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Graph orchestration failed: {e}", exc_info=True)

            # Mark version as failed
            if self._session and result.version_id:
                try:
                    version_mgr = GraphVersionManager(self._conn, self._session)
                    await version_mgr.fail_version(result.version_id, str(e))
                except Exception:
                    pass

        return result

    async def rebuild(
        self,
        df: pd.DataFrame,
        dataset_id: str | None = None,
        built_by: str = "system",
    ) -> OrchestrationResult:
        """Full rebuild (clear + build)."""
        return await self.build(df, dataset_id=dataset_id, clear_existing=True, built_by=built_by)

    async def update(
        self,
        df: pd.DataFrame,
        dataset_id: str | None = None,
        built_by: str = "system",
    ) -> OrchestrationResult:
        """Incremental update (MERGE without clear)."""
        return await self.build(df, dataset_id=dataset_id, clear_existing=False, built_by=built_by)

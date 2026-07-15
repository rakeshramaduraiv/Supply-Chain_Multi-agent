"""
AMASCI Neo4j Batch Loader
============================
High-performance batch loading with:
- Configurable batch sizes
- Progress tracking with callbacks
- Error recovery and partial commit
- Memory-efficient streaming
- Transaction isolation per batch
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.graph.connection import Neo4jConnectionManager
from app.graph.nodes import BaseNode
from app.graph.relationships import BaseRelationship
from app.graph.utils import chunk_list, utc_now_iso

logger = logging.getLogger(__name__)


@dataclass
class BatchProgress:
    """Tracks batch loading progress."""
    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    current_batch: int = 0
    total_batches: int = 0
    elapsed_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def progress_pct(self) -> float:
        return (self.processed_items / self.total_items * 100) if self.total_items > 0 else 0.0

    @property
    def items_per_second(self) -> float:
        return (self.processed_items / (self.elapsed_ms / 1000)) if self.elapsed_ms > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "current_batch": self.current_batch,
            "total_batches": self.total_batches,
            "progress_pct": round(self.progress_pct, 1),
            "items_per_second": round(self.items_per_second, 1),
            "elapsed_ms": round(self.elapsed_ms, 2),
            "errors": self.errors[:10],  # Cap error list
        }


@dataclass
class LoadResult:
    """Final result of a batch load operation."""
    nodes_loaded: dict[str, int] = field(default_factory=dict)
    relationships_loaded: dict[str, int] = field(default_factory=dict)
    total_nodes: int = 0
    total_relationships: int = 0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    batches_executed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes_loaded": self.nodes_loaded,
            "relationships_loaded": self.relationships_loaded,
            "total_nodes": self.total_nodes,
            "total_relationships": self.total_relationships,
            "duration_ms": round(self.duration_ms, 2),
            "errors": self.errors[:20],
            "batches_executed": self.batches_executed,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CYPHER TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

_MERGE_NODE = """
    UNWIND $batch AS props
    MERGE (n:{label} {{node_id: props.node_id}})
    SET n += props, n.updated_at = $now
    RETURN count(n) AS cnt
"""

_MERGE_RELATIONSHIP = """
    UNWIND $batch AS rel
    MATCH (a:{source_label} {{node_id: rel.source_id}})
    MATCH (b:{target_label} {{node_id: rel.target_id}})
    MERGE (a)-[r:{rel_type}]->(b)
    SET r.relationship_strength = rel.relationship_strength,
        r.frequency = rel.frequency,
        r.avg_delay = coalesce(rel.avg_delay, 0.0),
        r.confidence = rel.confidence,
        r.created_at = coalesce(r.created_at, rel.created_at),
        r.updated_at = rel.updated_at
    RETURN count(r) AS cnt
"""


class BatchLoader:
    """
    High-performance batch loader for Neo4j Knowledge Graph.

    Features:
    - Configurable batch size (default 500, max 5000)
    - Progress callback for real-time tracking
    - Per-batch transaction isolation (partial failures don't roll back all)
    - Automatic retry on transient failures
    - Memory-efficient: processes one batch at a time
    """

    def __init__(
        self,
        connection: Neo4jConnectionManager,
        batch_size: int = 500,
        max_retries: int = 2,
        on_progress: Callable[[BatchProgress], None] | None = None,
    ):
        self._conn = connection
        self._batch_size = min(max(batch_size, 50), 5000)
        self._max_retries = max_retries
        self._on_progress = on_progress

    async def load_nodes(self, nodes: list[BaseNode], label: str) -> int:
        """Load nodes of a single label in batches."""
        if not nodes:
            return 0

        query = _MERGE_NODE.format(label=label)
        items = [n.to_dict() for n in nodes]
        batches = chunk_list(items, self._batch_size)
        now = utc_now_iso()

        progress = BatchProgress(
            total_items=len(items),
            total_batches=len(batches),
        )
        start = time.perf_counter()
        total_created = 0

        for i, batch in enumerate(batches):
            progress.current_batch = i + 1
            count = await self._execute_batch_with_retry(query, {"batch": batch, "now": now})
            total_created += count
            progress.processed_items += len(batch)
            progress.successful_items += count
            progress.failed_items += len(batch) - count
            progress.elapsed_ms = (time.perf_counter() - start) * 1000
            self._emit_progress(progress)

        logger.info(f"Loaded {total_created} {label} nodes in {len(batches)} batches")
        return total_created

    async def load_relationships(self, relationships: list[BaseRelationship]) -> dict[str, int]:
        """Load relationships grouped by type in batches."""
        if not relationships:
            return {}

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

        results: dict[str, int] = {}
        total_items = sum(len(v) for v in grouped.values())
        progress = BatchProgress(total_items=total_items)
        start = time.perf_counter()

        for (rel_type, source_label, target_label), rel_items in grouped.items():
            query = _MERGE_RELATIONSHIP.format(
                source_label=source_label,
                target_label=target_label,
                rel_type=rel_type,
            )
            batches = chunk_list(rel_items, self._batch_size)
            progress.total_batches += len(batches)
            type_count = 0

            for batch in batches:
                progress.current_batch += 1
                count = await self._execute_batch_with_retry(query, {"batch": batch})
                type_count += count
                progress.processed_items += len(batch)
                progress.successful_items += count
                progress.elapsed_ms = (time.perf_counter() - start) * 1000
                self._emit_progress(progress)

            results[rel_type] = type_count

        logger.info(f"Loaded {sum(results.values())} relationships across {len(grouped)} types")
        return results

    async def load_all(
        self,
        node_groups: dict[str, list[BaseNode]],
        relationships: list[BaseRelationship],
    ) -> LoadResult:
        """
        Load all nodes and relationships in optimal order.

        Order: Nodes first (all labels), then relationships.
        """
        start = time.perf_counter()
        result = LoadResult()

        # Load nodes by label
        for label, nodes in node_groups.items():
            count = await self.load_nodes(nodes, label)
            result.nodes_loaded[label] = count
            result.total_nodes += count
            result.batches_executed += (len(nodes) // self._batch_size) + 1

        # Load relationships
        rel_counts = await self.load_relationships(relationships)
        result.relationships_loaded = rel_counts
        result.total_relationships = sum(rel_counts.values())

        result.duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Batch load complete: {result.total_nodes} nodes, "
            f"{result.total_relationships} rels in {result.duration_ms:.0f}ms"
        )
        return result

    async def _execute_batch_with_retry(self, query: str, params: dict[str, Any]) -> int:
        """Execute a batch query with retry on transient failures."""
        for attempt in range(self._max_retries + 1):
            try:
                records = await self._conn.execute_write(query, params)
                return records[0]["cnt"] if records else 0
            except Exception as e:
                if attempt < self._max_retries:
                    delay = 0.5 * (2 ** attempt)
                    logger.warning(f"Batch retry {attempt + 1}: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Batch failed after {self._max_retries + 1} attempts: {e}")
                    return 0

    def _emit_progress(self, progress: BatchProgress) -> None:
        """Emit progress to callback if registered."""
        if self._on_progress:
            try:
                self._on_progress(progress)
            except Exception:
                pass

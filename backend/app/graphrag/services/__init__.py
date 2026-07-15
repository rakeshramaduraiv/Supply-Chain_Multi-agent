"""
AMASCI GraphRAG Service Layer
================================
Orchestrates GraphRAG operations, delegates to GraphContextService.
"""

import logging
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graphrag.graph_context import GraphContextService
from app.graphrag.repositories import GraphRAGRepository
from app.graphrag.utils import PerformanceTimer, utc_now_iso

logger = logging.getLogger(__name__)


class GraphRAGService:
    """
    High-level service orchestrating all GraphRAG operations.

    Wraps GraphContextService with:
    - Request validation
    - History persistence
    - Metrics collection
    - Error handling
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        conn = connection or get_connection_manager()
        self._context_service = GraphContextService(conn)
        self._repository = GraphRAGRepository()

    async def get_context(
        self,
        entity_id: str,
        entity_label: str,
        context_type: str = "general",
        include_embedding: bool = False,
    ) -> dict[str, Any]:
        """Get structured graph context for an entity."""
        with PerformanceTimer("service.get_context") as timer:
            result = await self._context_service.get_context(entity_id, entity_label, context_type)

            if include_embedding and result.get("context"):
                result["embedding"] = self._context_service.get_context_embedding(
                    result["context"]
                )

        result["service_duration_ms"] = timer.duration_ms
        self._repository.save_context({
            "entity_id": entity_id,
            "entity_label": entity_label,
            "context_type": context_type,
            "duration_ms": timer.duration_ms,
        })
        return result

    async def execute_query(self, query_text: str) -> dict[str, Any]:
        """Execute a natural language or structured query."""
        with PerformanceTimer("service.execute_query") as timer:
            result = await self._context_service.query(query_text)

        result["service_duration_ms"] = timer.duration_ms
        self._repository.save_query({
            "query": query_text,
            "result_count": result.get("result_count", 0),
            "intent": result.get("intent", "unknown"),
            "duration_ms": timer.duration_ms,
        })
        return result

    async def get_subgraph(
        self, entity_id: str, entity_label: str, hops: int = 2
    ) -> dict[str, Any]:
        """Get subgraph around an entity."""
        return await self._context_service.get_subgraph(entity_id, entity_label, hops)

    async def get_dependencies(
        self, entity_id: str, entity_label: str, max_depth: int = 3
    ) -> dict[str, Any]:
        """Get dependency analysis."""
        return await self._context_service.get_dependencies(entity_id, entity_label, max_depth)

    async def get_forecast_context(
        self, entity_id: str, entity_label: str
    ) -> dict[str, Any]:
        """Get forecast-specific graph context."""
        return await self._context_service.get_forecast_context(entity_id, entity_label)

    async def get_risk_context(
        self, entity_id: str, entity_label: str
    ) -> dict[str, Any]:
        """Get risk reasoning context."""
        return await self._context_service.get_risk_context(entity_id, entity_label)

    async def get_root_cause_context(
        self, entity_id: str, entity_label: str, issue_type: str
    ) -> dict[str, Any]:
        """Get root cause analysis context."""
        return await self._context_service.get_root_cause_context(
            entity_id, entity_label, issue_type
        )

    async def get_impact_propagation(
        self, entity_id: str, entity_label: str, initial_risk: float = 1.0
    ) -> dict[str, Any]:
        """Get impact propagation analysis."""
        return await self._context_service.get_impact_propagation(
            entity_id, entity_label, initial_risk
        )

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get operation history."""
        return self._context_service.get_history(limit)

    def get_statistics(self) -> dict[str, Any]:
        """Get service statistics."""
        service_stats = self._context_service.get_statistics()
        repo_metrics = self._repository.get_metrics()
        return {
            **service_stats,
            "repository_metrics": repo_metrics,
        }

    def get_cache_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._context_service.get_cache_statistics()

    def invalidate_cache(self, prefix: str | None = None) -> dict[str, Any]:
        """Invalidate cache entries."""
        count = self._context_service.invalidate_cache(prefix)
        return {"invalidated": count, "prefix": prefix, "timestamp": utc_now_iso()}

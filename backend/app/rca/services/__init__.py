"""
AMASCI RCA Service Layer
===========================
High-level service orchestrating RCA operations with persistence.
"""

import logging
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.rca.engine import RCAEngine
from app.rca.repositories import RCARepository
from app.rca.utils import PerformanceTimer, RCAType, utc_now_iso

logger = logging.getLogger(__name__)


class RCAService:
    """
    High-level RCA service with persistence and metrics.

    Wraps RCAEngine with:
    - Input validation
    - Report persistence
    - History tracking
    - Statistics collection
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        conn = connection or get_connection_manager()
        self._engine = RCAEngine(conn)
        self._repository = RCARepository()

    async def analyze(
        self,
        target_id: str,
        target_label: str,
        rca_type: str,
        max_depth: int = 3,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """Execute full RCA analysis and persist the report."""
        # Validate rca_type
        valid_types = [t.value for t in RCAType]
        if rca_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid rca_type '{rca_type}'. Valid: {valid_types}",
            }

        report = await self._engine.analyze(
            target_id=target_id,
            target_label=target_label,
            rca_type=rca_type,
            max_depth=max_depth,
            top_n=top_n,
        )

        # Persist
        self._repository.save_report(report)

        return {"success": True, "report": report.to_dict()}

    async def get_subgraph(
        self, target_id: str, target_label: str, hops: int = 2
    ) -> dict[str, Any]:
        """Get RCA-relevant subgraph."""
        result = await self._engine.get_subgraph(target_id, target_label, hops)
        return {"success": True, "subgraph": result}

    async def get_path(
        self, source_id: str, target_id: str
    ) -> dict[str, Any]:
        """Get path between two nodes."""
        result = await self._engine.get_path(source_id, target_id)
        return {"success": True, "path": result}

    def get_latest(self) -> dict[str, Any]:
        """Get the most recent RCA report."""
        report = self._repository.get_latest()
        if not report:
            return {"success": False, "error": "No RCA reports available"}
        return {"success": True, "report": report}

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get RCA analysis history."""
        return self._repository.get_history(limit)

    def get_statistics(self) -> dict[str, Any]:
        """Get RCA service statistics."""
        return self._repository.get_metrics()

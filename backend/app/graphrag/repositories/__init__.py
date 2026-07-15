"""
AMASCI GraphRAG Repository
=============================
Data access layer for GraphRAG-specific persistence (history, cached contexts).
"""

import logging
from typing import Any

from app.graphrag.utils import utc_now_iso

logger = logging.getLogger(__name__)


class GraphRAGRepository:
    """
    Repository for GraphRAG operation persistence.

    Stores:
    - Query history
    - Context generation history
    - Cached structured contexts
    - Operation metrics
    """

    def __init__(self):
        self._query_history: list[dict[str, Any]] = []
        self._context_history: list[dict[str, Any]] = []
        self._metrics: dict[str, Any] = {
            "total_queries": 0,
            "total_contexts": 0,
            "total_subgraphs": 0,
            "total_dependencies": 0,
            "avg_query_ms": 0.0,
            "avg_context_ms": 0.0,
        }

    def save_query(self, query_data: dict[str, Any]) -> str:
        """Save a query execution record."""
        record = {
            "id": f"q_{len(self._query_history)}",
            "timestamp": utc_now_iso(),
            **query_data,
        }
        self._query_history.append(record)
        self._metrics["total_queries"] += 1
        self._update_avg("avg_query_ms", query_data.get("duration_ms", 0))
        return record["id"]

    def save_context(self, context_data: dict[str, Any]) -> str:
        """Save a context generation record."""
        record = {
            "id": f"c_{len(self._context_history)}",
            "timestamp": utc_now_iso(),
            **context_data,
        }
        self._context_history.append(record)
        self._metrics["total_contexts"] += 1
        self._update_avg("avg_context_ms", context_data.get("duration_ms", 0))
        return record["id"]

    def get_query_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent query history."""
        return self._query_history[-limit:]

    def get_context_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent context generation history."""
        return self._context_history[-limit:]

    def get_metrics(self) -> dict[str, Any]:
        """Get repository metrics."""
        return {**self._metrics}

    def clear_history(self) -> None:
        """Clear all history."""
        self._query_history.clear()
        self._context_history.clear()

    def _update_avg(self, key: str, new_value: float) -> None:
        """Update running average."""
        count_key = "total_queries" if "query" in key else "total_contexts"
        count = self._metrics[count_key]
        if count <= 1:
            self._metrics[key] = new_value
        else:
            old_avg = self._metrics[key]
            self._metrics[key] = old_avg + (new_value - old_avg) / count

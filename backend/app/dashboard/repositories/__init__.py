"""
AMASCI Dashboard Repository
===============================
In-memory data store for dashboard analytics state.
"""

import logging
from typing import Any

from app.dashboard.utils import utc_now_iso

logger = logging.getLogger(__name__)


class DashboardRepository:
    """
    Repository for dashboard analytics persistence.

    Stores:
    - Latest KPI snapshots
    - Forecast history
    - TPKE evolution history
    - RCA report summaries
    - Comparison baselines
    """

    def __init__(self):
        self._kpi_history: list[dict[str, Any]] = []
        self._forecast_history: list[dict[str, Any]] = []
        self._tpke_history: list[dict[str, Any]] = []
        self._rca_summaries: list[dict[str, Any]] = []
        self._comparison_baselines: dict[str, dict[str, Any]] = {}
        self._last_refresh: str = ""

    def save_kpi_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._kpi_history.append({"timestamp": utc_now_iso(), **snapshot})
        if len(self._kpi_history) > 500:
            self._kpi_history = self._kpi_history[-250:]

    def save_forecast_record(self, record: dict[str, Any]) -> None:
        self._forecast_history.append({"timestamp": utc_now_iso(), **record})
        if len(self._forecast_history) > 500:
            self._forecast_history = self._forecast_history[-250:]

    def save_tpke_record(self, record: dict[str, Any]) -> None:
        self._tpke_history.append({"timestamp": utc_now_iso(), **record})

    def save_rca_summary(self, summary: dict[str, Any]) -> None:
        self._rca_summaries.append({"timestamp": utc_now_iso(), **summary})

    def set_baseline(self, key: str, data: dict[str, Any]) -> None:
        self._comparison_baselines[key] = {"timestamp": utc_now_iso(), **data}

    def get_baseline(self, key: str) -> dict[str, Any] | None:
        return self._comparison_baselines.get(key)

    def get_kpi_history(self, limit: int = 30) -> list[dict[str, Any]]:
        return self._kpi_history[-limit:]

    def get_forecast_history(self, limit: int = 30) -> list[dict[str, Any]]:
        return self._forecast_history[-limit:]

    def get_tpke_history(self, limit: int = 30) -> list[dict[str, Any]]:
        return self._tpke_history[-limit:]

    def get_rca_summaries(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._rca_summaries[-limit:]

    def mark_refresh(self) -> None:
        self._last_refresh = utc_now_iso()

    @property
    def last_refresh(self) -> str:
        return self._last_refresh

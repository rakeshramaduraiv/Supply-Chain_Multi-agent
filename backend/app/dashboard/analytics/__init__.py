"""
AMASCI Dashboard Analytics Engine
====================================
Core analytics aggregation from all system modules.
"""

import logging
from typing import Any

from app.dashboard.utils import PerformanceTimer, utc_now_iso, format_chart_series

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Central analytics aggregation engine.

    Collects and formats data from:
    - ML predictions and metrics
    - Graph statistics
    - TPKE evolution data
    - RCA reports
    - Forecast results
    """

    def __init__(self):
        self._ml_metrics: dict[str, Any] = {}
        self._graph_stats: dict[str, Any] = {}
        self._tpke_stats: dict[str, Any] = {}
        self._rca_stats: dict[str, Any] = {}
        self._forecast_metrics: dict[str, Any] = {}

    def update_ml_metrics(self, metrics: dict[str, Any]) -> None:
        self._ml_metrics = {**self._ml_metrics, **metrics}

    def update_graph_stats(self, stats: dict[str, Any]) -> None:
        self._graph_stats = {**self._graph_stats, **stats}

    def update_tpke_stats(self, stats: dict[str, Any]) -> None:
        self._tpke_stats = {**self._tpke_stats, **stats}

    def update_rca_stats(self, stats: dict[str, Any]) -> None:
        self._rca_stats = {**self._rca_stats, **stats}

    def update_forecast_metrics(self, metrics: dict[str, Any]) -> None:
        self._forecast_metrics = {**self._forecast_metrics, **metrics}

    def get_ml_metrics(self) -> dict[str, Any]:
        return {**self._ml_metrics}

    def get_graph_stats(self) -> dict[str, Any]:
        return {**self._graph_stats}

    def get_tpke_stats(self) -> dict[str, Any]:
        return {**self._tpke_stats}

    def get_rca_stats(self) -> dict[str, Any]:
        return {**self._rca_stats}

    def get_forecast_metrics(self) -> dict[str, Any]:
        return {**self._forecast_metrics}

    def get_all_metrics(self) -> dict[str, Any]:
        return {
            "ml": self._ml_metrics,
            "graph": self._graph_stats,
            "tpke": self._tpke_stats,
            "rca": self._rca_stats,
            "forecast": self._forecast_metrics,
            "collected_at": utc_now_iso(),
        }

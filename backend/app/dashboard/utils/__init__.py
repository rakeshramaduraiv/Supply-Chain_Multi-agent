"""
AMASCI Dashboard Utilities
=============================
Shared helpers for the Dashboard module.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def compute_health_score(metrics: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Compute weighted health score from multiple metrics."""
    if not metrics:
        return 0.0
    if weights is None:
        weights = {k: 1.0 / len(metrics) for k in metrics}
    total = sum(metrics.get(k, 0.0) * weights.get(k, 0.0) for k in metrics)
    return round(min(1.0, max(0.0, total)), 4)


def compute_trend(values: list[float]) -> str:
    """Determine trend direction from a series of values."""
    if len(values) < 2:
        return "stable"
    recent = values[-3:] if len(values) >= 3 else values
    avg_recent = sum(recent) / len(recent)
    avg_all = sum(values) / len(values)
    diff = (avg_recent - avg_all) / max(abs(avg_all), 0.001)
    if diff > 0.05:
        return "increasing"
    elif diff < -0.05:
        return "decreasing"
    return "stable"


def compute_change_pct(current: float, previous: float) -> float:
    """Compute percentage change."""
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - previous) / abs(previous)) * 100, 2)


def risk_label(score: float) -> str:
    if score >= 0.75:
        return "critical"
    elif score >= 0.50:
        return "high"
    elif score >= 0.25:
        return "medium"
    return "low"


def format_card(title: str, value: Any, unit: str = "", trend: str = "stable", change_pct: float = 0.0) -> dict[str, Any]:
    """Format a dashboard summary card."""
    return {
        "title": title,
        "value": value,
        "unit": unit,
        "trend": trend,
        "change_pct": change_pct,
    }


def format_chart_series(name: str, labels: list[str], values: list[float]) -> dict[str, Any]:
    """Format a chart-ready time series."""
    return {"name": name, "labels": labels, "values": values}


def format_table_row(columns: dict[str, Any]) -> dict[str, Any]:
    """Format a table-ready row."""
    return columns


class PerformanceTimer:
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        logger.debug(f"[Dashboard] {self.operation}: {self.duration_ms:.2f}ms")

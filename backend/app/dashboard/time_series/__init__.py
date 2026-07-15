"""
AMASCI Time Series Module
============================
Time series formatting for dashboard charts.
"""

from typing import Any
from app.dashboard.utils import format_chart_series, utc_now_iso


class TimeSeriesEngine:
    """Formats time series data for dashboard consumption."""

    def format_series(self, name: str, data: list[dict[str, Any]], value_key: str = "value", label_key: str = "label") -> dict[str, Any]:
        labels = [d.get(label_key, f"P{i}") for i, d in enumerate(data)]
        values = [float(d.get(value_key, 0.0)) for d in data]
        return format_chart_series(name, labels, values)

    def format_multi_series(self, series_configs: list[dict[str, Any]], data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for config in series_configs:
            name = config.get("name", "Series")
            value_key = config.get("value_key", "value")
            labels = [d.get("label", f"P{i}") for i, d in enumerate(data)]
            values = [float(d.get(value_key, 0.0)) for d in data]
            result.append(format_chart_series(name, labels, values))
        return result

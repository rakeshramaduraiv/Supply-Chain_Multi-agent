"""
AMASCI Trend Analysis
========================
Daily, weekly, monthly, quarterly, yearly trend computation.
"""

from typing import Any
from app.dashboard.utils import compute_trend, compute_change_pct, format_chart_series, utc_now_iso


class TrendAnalysisEngine:
    """Computes trends across multiple time granularities."""

    def generate(self, time_series_data: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        data = time_series_data or []

        values = [d.get("value", 0.0) for d in data]
        labels = [d.get("label", "") for d in data]

        daily = self._aggregate(data, "daily")
        weekly = self._aggregate(data, "weekly")
        monthly = self._aggregate(data, "monthly")

        return {
            "overall_trend": compute_trend(values),
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
            "charts": [
                format_chart_series("Trend", labels[-30:], values[-30:]),
            ] if values else [],
            "generated_at": utc_now_iso(),
        }

    def _aggregate(self, data: list[dict[str, Any]], granularity: str) -> dict[str, Any]:
        values = [d.get("value", 0.0) for d in data]
        if not values:
            return {"trend": "stable", "change_pct": 0.0, "data_points": 0}

        if granularity == "daily":
            recent = values[-7:]
        elif granularity == "weekly":
            recent = values[-28:]
        else:
            recent = values

        trend = compute_trend(recent)
        current = sum(recent[-len(recent)//2:]) / max(len(recent)//2, 1) if recent else 0
        previous = sum(recent[:len(recent)//2]) / max(len(recent)//2, 1) if recent else 0
        change = compute_change_pct(current, previous)

        return {
            "trend": trend,
            "change_pct": change,
            "data_points": len(recent),
            "current_avg": round(current, 4),
            "previous_avg": round(previous, 4),
        }

"""
AMASCI Forecast Dashboard
============================
Forecast analytics: demand trends, accuracy, history.
"""

from typing import Any
from app.dashboard.utils import format_card, format_chart_series, compute_trend, utc_now_iso


class ForecastDashboard:
    """Generates forecast analytics for the dashboard."""

    def generate(self, forecast_metrics: dict[str, Any], forecast_history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        history = forecast_history or []
        mape = forecast_metrics.get("mape", 15.0)
        rmse = forecast_metrics.get("rmse", 0.0)
        accuracy = 1.0 - mape / 100.0 if mape < 100 else 0.0
        confidence = forecast_metrics.get("avg_confidence", 0.7)

        demand_values = [h.get("demand", 0) for h in history if "demand" in h]
        trend = compute_trend(demand_values) if demand_values else "stable"

        cards = [
            format_card("Forecast Accuracy", f"{accuracy:.0%}"),
            format_card("MAPE", f"{mape:.1f}%"),
            format_card("RMSE", f"{rmse:.4f}"),
            format_card("Confidence", f"{confidence:.0%}"),
            format_card("Demand Trend", trend),
        ]

        charts = []
        if demand_values:
            labels = [h.get("period", f"P{i}") for i, h in enumerate(history)]
            charts.append(format_chart_series("Demand", labels, demand_values))

        return {
            "cards": cards,
            "charts": charts,
            "metrics": {
                "mape": round(mape, 2),
                "rmse": round(rmse, 4),
                "accuracy": round(accuracy, 4),
                "confidence": round(confidence, 4),
                "demand_trend": trend,
                "demand_growth": self._compute_growth(demand_values),
            },
            "history": history[-12:],
            "generated_at": utc_now_iso(),
        }

    def _compute_growth(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        first_half = sum(values[:len(values)//2]) / max(len(values)//2, 1)
        second_half = sum(values[len(values)//2:]) / max(len(values) - len(values)//2, 1)
        if first_half == 0:
            return 0.0
        return round((second_half - first_half) / first_half * 100, 2)

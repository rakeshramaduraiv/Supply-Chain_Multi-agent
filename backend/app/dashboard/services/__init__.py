"""
AMASCI Dashboard Service Layer
=================================
Orchestrates all dashboard analytics operations.
"""

import logging
from typing import Any

from app.dashboard.analytics import AnalyticsEngine
from app.dashboard.comparison import ComparisonEngine
from app.dashboard.executive_summary import ExecutiveSummaryEngine
from app.dashboard.export import ExportEngine
from app.dashboard.forecast_dashboard import ForecastDashboard
from app.dashboard.graph_dashboard import GraphDashboard
from app.dashboard.kpi import KPIEngine
from app.dashboard.rca_dashboard import RCADashboard
from app.dashboard.repositories import DashboardRepository
from app.dashboard.risk_dashboard import RiskDashboard
from app.dashboard.time_series import TimeSeriesEngine
from app.dashboard.tpke_dashboard import TPKEDashboard
from app.dashboard.trend_analysis import TrendAnalysisEngine
from app.dashboard.utils import PerformanceTimer, utc_now_iso

logger = logging.getLogger(__name__)


class DashboardService:
    """
    Orchestrates all dashboard analytics.

    Aggregates data from ML, Graph, TPKE, RCA, Forecast modules
    and produces chart-ready, table-ready, card-ready outputs.
    """

    def __init__(self):
        self._analytics = AnalyticsEngine()
        self._kpi = KPIEngine()
        self._executive = ExecutiveSummaryEngine()
        self._forecast = ForecastDashboard()
        self._risk = RiskDashboard()
        self._graph = GraphDashboard()
        self._tpke = TPKEDashboard()
        self._rca = RCADashboard()
        self._trends = TrendAnalysisEngine()
        self._comparison = ComparisonEngine()
        self._export = ExportEngine()
        self._time_series = TimeSeriesEngine()
        self._repository = DashboardRepository()

    # --- Data Ingestion ---

    def ingest_ml_metrics(self, metrics: dict[str, Any]) -> None:
        self._analytics.update_ml_metrics(metrics)

    def ingest_graph_stats(self, stats: dict[str, Any]) -> None:
        self._analytics.update_graph_stats(stats)

    def ingest_tpke_stats(self, stats: dict[str, Any]) -> None:
        self._analytics.update_tpke_stats(stats)

    def ingest_rca_stats(self, stats: dict[str, Any]) -> None:
        self._analytics.update_rca_stats(stats)

    def ingest_forecast_metrics(self, metrics: dict[str, Any]) -> None:
        self._analytics.update_forecast_metrics(metrics)

    # --- Dashboard Endpoints ---

    def get_full_dashboard(self) -> dict[str, Any]:
        """Get complete dashboard data."""
        with PerformanceTimer("full_dashboard") as timer:
            kpis = self.get_kpis()
            executive = self.get_executive_summary()

        return {
            "kpis": kpis,
            "executive_summary": executive,
            "last_refresh": self._repository.last_refresh or utc_now_iso(),
            "duration_ms": round(timer.duration_ms, 2),
            "generated_at": utc_now_iso(),
        }

    def get_kpis(self) -> dict[str, Any]:
        """Get all KPIs."""
        kpis = self._kpi.compute_all_kpis(
            ml_metrics=self._analytics.get_ml_metrics(),
            graph_stats=self._analytics.get_graph_stats(),
            tpke_stats=self._analytics.get_tpke_stats(),
            rca_stats=self._analytics.get_rca_stats(),
            forecast_metrics=self._analytics.get_forecast_metrics(),
        )
        self._repository.save_kpi_snapshot(kpis)
        return kpis

    def get_kpi_cards(self) -> list[dict[str, Any]]:
        """Get KPI summary cards."""
        kpis = self.get_kpis()
        return self._kpi.get_summary_cards(kpis)

    def get_executive_summary(self) -> dict[str, Any]:
        """Get executive summary."""
        kpis = self._kpi.compute_all_kpis(
            ml_metrics=self._analytics.get_ml_metrics(),
            graph_stats=self._analytics.get_graph_stats(),
            tpke_stats=self._analytics.get_tpke_stats(),
            rca_stats=self._analytics.get_rca_stats(),
            forecast_metrics=self._analytics.get_forecast_metrics(),
        )
        return self._executive.generate(kpis)

    def get_forecast_dashboard(self) -> dict[str, Any]:
        """Get forecast analytics."""
        return self._forecast.generate(
            self._analytics.get_forecast_metrics(),
            self._repository.get_forecast_history(),
        )

    def get_risk_dashboard(self) -> dict[str, Any]:
        """Get risk analytics."""
        return self._risk.generate(
            self._analytics.get_ml_metrics(),
            self._analytics.get_rca_stats(),
        )

    def get_graph_dashboard(self) -> dict[str, Any]:
        """Get graph analytics."""
        return self._graph.generate(self._analytics.get_graph_stats())

    def get_tpke_dashboard(self) -> dict[str, Any]:
        """Get TPKE analytics."""
        return self._tpke.generate(
            self._analytics.get_tpke_stats(),
            self._repository.get_tpke_history(),
        )

    def get_rca_dashboard(self) -> dict[str, Any]:
        """Get RCA analytics."""
        return self._rca.generate(
            self._analytics.get_rca_stats(),
            self._repository.get_rca_summaries(),
        )

    def get_trends(self, data: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Get trend analysis."""
        return self._trends.generate(data)

    def get_comparison(
        self, comparison_type: str, current: dict[str, Any], previous: dict[str, Any]
    ) -> dict[str, Any]:
        """Get comparison analytics."""
        if comparison_type == "prediction_vs_actual":
            return self._comparison.compare_prediction_vs_actual(
                current.get("predictions", []), previous.get("actuals", [])
            )
        elif comparison_type == "period":
            return self._comparison.compare_periods(current, previous)
        elif comparison_type == "tpke_impact":
            return self._comparison.compare_tpke_impact(current, previous)
        elif comparison_type == "graph_versions":
            return self._comparison.compare_graph_versions(current, previous)
        return {"error": f"Unknown comparison type: {comparison_type}"}

    def export_data(self, format_type: str, data: Any = None) -> dict[str, Any]:
        """Export dashboard data."""
        if data is None:
            data = self.get_full_dashboard()

        if format_type == "csv" and isinstance(data, list):
            return self._export.export_csv(data)
        elif format_type == "json":
            return self._export.export_json(data)
        elif format_type == "tsv" and isinstance(data, list):
            return self._export.export_excel_tsv(data)
        elif format_type == "report":
            return self._export.export_report_text(data if isinstance(data, dict) else {"data": data})
        elif format_type == "snapshot":
            return self._export.export_snapshot(data if isinstance(data, dict) else {"data": data})
        return self._export.export_json(data)

    def refresh(self) -> dict[str, Any]:
        """Trigger a dashboard refresh."""
        self._repository.mark_refresh()
        return {
            "refreshed": True,
            "timestamp": utc_now_iso(),
            "metrics": self._analytics.get_all_metrics(),
        }

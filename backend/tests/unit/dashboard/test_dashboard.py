"""
AMASCI Dashboard Unit Tests
===============================
Tests for KPI, analytics, executive summary, export, comparison, and trend engines.
"""

import pytest
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
from app.dashboard.services import DashboardService
from app.dashboard.time_series import TimeSeriesEngine
from app.dashboard.tpke_dashboard import TPKEDashboard
from app.dashboard.trend_analysis import TrendAnalysisEngine
from app.dashboard.utils import (
    compute_change_pct, compute_health_score, compute_trend,
    format_card, format_chart_series, risk_label,
)


# --- Utils Tests ---

class TestUtils:
    def test_compute_health_score(self):
        score = compute_health_score({"a": 0.8, "b": 0.6})
        assert 0.0 <= score <= 1.0

    def test_compute_health_score_empty(self):
        assert compute_health_score({}) == 0.0

    def test_compute_trend_increasing(self):
        assert compute_trend([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == "increasing"

    def test_compute_trend_decreasing(self):
        assert compute_trend([10, 9, 8, 7, 6, 5, 4, 3, 2, 1]) == "decreasing"

    def test_compute_trend_stable(self):
        assert compute_trend([5, 5, 5, 5, 5]) == "stable"

    def test_compute_trend_short(self):
        assert compute_trend([5]) == "stable"

    def test_compute_change_pct(self):
        assert compute_change_pct(110, 100) == 10.0
        assert compute_change_pct(90, 100) == -10.0
        assert compute_change_pct(0, 0) == 0.0

    def test_risk_label(self):
        assert risk_label(0.8) == "critical"
        assert risk_label(0.6) == "high"
        assert risk_label(0.3) == "medium"
        assert risk_label(0.1) == "low"

    def test_format_card(self):
        card = format_card("Test", 42, unit="items")
        assert card["title"] == "Test"
        assert card["value"] == 42
        assert card["unit"] == "items"

    def test_format_chart_series(self):
        series = format_chart_series("Sales", ["Jan", "Feb"], [100, 200])
        assert series["name"] == "Sales"
        assert len(series["labels"]) == 2
        assert len(series["values"]) == 2


# --- KPI Engine Tests ---

class TestKPIEngine:
    def setup_method(self):
        self.engine = KPIEngine()

    def test_compute_all_kpis_defaults(self):
        kpis = self.engine.compute_all_kpis()
        assert "overall_health" in kpis
        assert "supply_chain" in kpis
        assert "risk" in kpis
        assert "graph" in kpis
        assert "tpke" in kpis
        assert "prediction" in kpis
        assert 0.0 <= kpis["overall_health"] <= 1.0

    def test_compute_all_kpis_with_data(self):
        kpis = self.engine.compute_all_kpis(
            ml_metrics={"accuracy": 0.85, "avg_supplier_delay_rate": 0.2},
            graph_stats={"total_nodes": 100, "total_relationships": 500, "graph_density": 0.05},
            tpke_stats={"evolution_cycles": 3, "edges_added": 10},
            forecast_metrics={"mape": 12.0, "avg_volatility": 0.2},
        )
        assert kpis["overall_health"] > 0
        assert kpis["graph"]["total_nodes"] == 100

    def test_get_summary_cards(self):
        kpis = self.engine.compute_all_kpis()
        cards = self.engine.get_summary_cards(kpis)
        assert len(cards) >= 5
        assert all("title" in c for c in cards)


# --- Executive Summary Tests ---

class TestExecutiveSummary:
    def setup_method(self):
        self.engine = ExecutiveSummaryEngine()

    def test_generate_summary(self):
        kpis = KPIEngine().compute_all_kpis()
        summary = self.engine.generate(kpis)
        assert "top_operational_risks" in summary
        assert "monthly_highlights" in summary
        assert "system_recommendations" in summary
        assert len(summary["top_operational_risks"]) <= 5

    def test_recommendations_generated(self):
        kpis = KPIEngine().compute_all_kpis(
            ml_metrics={"avg_supplier_risk": 0.6, "avg_late_delivery_rate": 0.7}
        )
        summary = self.engine.generate(kpis)
        assert len(summary["system_recommendations"]) > 0


# --- Analytics Engine Tests ---

class TestAnalyticsEngine:
    def setup_method(self):
        self.engine = AnalyticsEngine()

    def test_update_and_get_ml_metrics(self):
        self.engine.update_ml_metrics({"accuracy": 0.9})
        assert self.engine.get_ml_metrics()["accuracy"] == 0.9

    def test_update_and_get_graph_stats(self):
        self.engine.update_graph_stats({"total_nodes": 50})
        assert self.engine.get_graph_stats()["total_nodes"] == 50

    def test_get_all_metrics(self):
        self.engine.update_ml_metrics({"x": 1})
        self.engine.update_graph_stats({"y": 2})
        all_m = self.engine.get_all_metrics()
        assert "ml" in all_m
        assert "graph" in all_m
        assert "collected_at" in all_m


# --- Forecast Dashboard Tests ---

class TestForecastDashboard:
    def setup_method(self):
        self.dashboard = ForecastDashboard()

    def test_generate_empty(self):
        result = self.dashboard.generate({})
        assert "cards" in result
        assert "metrics" in result

    def test_generate_with_data(self):
        result = self.dashboard.generate(
            {"mape": 10.0, "rmse": 0.5, "avg_confidence": 0.8},
            [{"demand": 100, "period": "Jan"}, {"demand": 120, "period": "Feb"}],
        )
        assert result["metrics"]["mape"] == 10.0
        assert len(result["charts"]) > 0


# --- Risk Dashboard Tests ---

class TestRiskDashboard:
    def setup_method(self):
        self.dashboard = RiskDashboard()

    def test_generate(self):
        result = self.dashboard.generate({"avg_late_delivery_rate": 0.5})
        assert "overall_risk" in result
        assert "breakdown" in result
        assert len(result["breakdown"]) == 7


# --- Graph Dashboard Tests ---

class TestGraphDashboard:
    def setup_method(self):
        self.dashboard = GraphDashboard()

    def test_generate(self):
        result = self.dashboard.generate({
            "total_nodes": 200,
            "total_relationships": 800,
            "graph_density": 0.02,
            "node_counts": {"Supplier": 50, "Product": 100},
            "relationship_counts": {"SUPPLIES": 300, "STORED_IN": 200},
        })
        assert result["metrics"]["total_nodes"] == 200
        assert len(result["node_distribution"]) == 2


# --- TPKE Dashboard Tests ---

class TestTPKEDashboard:
    def setup_method(self):
        self.dashboard = TPKEDashboard()

    def test_generate(self):
        result = self.dashboard.generate({"edges_added": 5, "evolution_cycles": 2})
        assert result["metrics"]["edges_added"] == 5
        assert len(result["cards"]) >= 5


# --- RCA Dashboard Tests ---

class TestRCADashboard:
    def setup_method(self):
        self.dashboard = RCADashboard()

    def test_generate_empty(self):
        result = self.dashboard.generate({})
        assert "metrics" in result
        assert "type_distribution" in result

    def test_generate_with_history(self):
        result = self.dashboard.generate(
            {"total_analyses": 3, "analyses_by_type": {"late_delivery": 2}},
            [{"primary_root_cause": {"label": "Supplier", "node_id": "abc123"}}],
        )
        assert result["metrics"]["total_analyses"] == 3


# --- Trend Analysis Tests ---

class TestTrendAnalysis:
    def setup_method(self):
        self.engine = TrendAnalysisEngine()

    def test_generate_empty(self):
        result = self.engine.generate()
        assert result["overall_trend"] == "stable"

    def test_generate_with_data(self):
        data = [{"value": i * 1.1, "label": f"D{i}"} for i in range(30)]
        result = self.engine.generate(data)
        assert result["overall_trend"] in ("increasing", "stable", "decreasing")
        assert "daily" in result


# --- Comparison Engine Tests ---

class TestComparisonEngine:
    def setup_method(self):
        self.engine = ComparisonEngine()

    def test_prediction_vs_actual(self):
        result = self.engine.compare_prediction_vs_actual(
            [10, 20, 30], [12, 18, 33]
        )
        assert "mae" in result
        assert "mape" in result
        assert result["sample_size"] == 3

    def test_compare_periods(self):
        result = self.engine.compare_periods(
            {"sales": 100, "orders": 50},
            {"sales": 90, "orders": 45},
        )
        assert "metrics" in result
        assert result["metrics"]["sales"]["direction"] == "up"

    def test_compare_tpke_impact(self):
        result = self.engine.compare_tpke_impact(
            {"accuracy": 0.7}, {"accuracy": 0.85}
        )
        assert result["metrics"]["accuracy"]["improvement_pct"] > 0

    def test_compare_graph_versions(self):
        result = self.engine.compare_graph_versions(
            {"total_nodes": 100, "total_relationships": 400, "graph_density": 0.04},
            {"total_nodes": 120, "total_relationships": 500, "graph_density": 0.05, "inferred_edge_count": 20},
        )
        assert result["delta"]["node_growth"] == 20


# --- Export Engine Tests ---

class TestExportEngine:
    def setup_method(self):
        self.engine = ExportEngine()

    def test_export_csv(self):
        data = [{"name": "A", "value": 1}, {"name": "B", "value": 2}]
        result = self.engine.export_csv(data)
        assert result["format"] == "csv"
        assert result["rows"] == 2
        assert "name,value" in result["content"] or "name\tvalue" in result["content"] or "A" in result["content"]

    def test_export_json(self):
        result = self.engine.export_json({"key": "value"})
        assert result["format"] == "json"
        assert "key" in result["content"]

    def test_export_tsv(self):
        data = [{"col1": "x", "col2": "y"}]
        result = self.engine.export_excel_tsv(data)
        assert result["format"] == "tsv"
        assert "\t" in result["content"]

    def test_export_report(self):
        result = self.engine.export_report_text({"kpis": {"overall_health": 0.8}})
        assert "AMASCI" in result["content"]

    def test_export_empty(self):
        result = self.engine.export_csv([])
        assert result["rows"] == 0


# --- Repository Tests ---

class TestDashboardRepository:
    def setup_method(self):
        self.repo = DashboardRepository()

    def test_save_and_get_kpi(self):
        self.repo.save_kpi_snapshot({"health": 0.8})
        history = self.repo.get_kpi_history()
        assert len(history) == 1
        assert history[0]["health"] == 0.8

    def test_mark_refresh(self):
        self.repo.mark_refresh()
        assert self.repo.last_refresh != ""


# --- Service Integration Tests ---

class TestDashboardService:
    def setup_method(self):
        self.service = DashboardService()

    def test_get_full_dashboard(self):
        result = self.service.get_full_dashboard()
        assert "kpis" in result
        assert "executive_summary" in result
        assert "generated_at" in result

    def test_get_kpis(self):
        kpis = self.service.get_kpis()
        assert "overall_health" in kpis

    def test_get_executive_summary(self):
        summary = self.service.get_executive_summary()
        assert "system_recommendations" in summary

    def test_get_forecast_dashboard(self):
        result = self.service.get_forecast_dashboard()
        assert "cards" in result

    def test_get_risk_dashboard(self):
        result = self.service.get_risk_dashboard()
        assert "overall_risk" in result

    def test_get_graph_dashboard(self):
        result = self.service.get_graph_dashboard()
        assert "metrics" in result

    def test_get_tpke_dashboard(self):
        result = self.service.get_tpke_dashboard()
        assert "metrics" in result

    def test_get_rca_dashboard(self):
        result = self.service.get_rca_dashboard()
        assert "metrics" in result

    def test_get_trends(self):
        result = self.service.get_trends()
        assert "overall_trend" in result

    def test_ingest_and_reflect(self):
        self.service.ingest_ml_metrics({"accuracy": 0.92})
        self.service.ingest_graph_stats({"total_nodes": 300})
        kpis = self.service.get_kpis()
        assert kpis["prediction"]["accuracy"] == 0.92
        assert kpis["graph"]["total_nodes"] == 300

    def test_export_json(self):
        result = self.service.export_data("json")
        assert result["format"] == "json"

    def test_export_report(self):
        result = self.service.export_data("report")
        assert result["format"] == "txt"

    def test_refresh(self):
        result = self.service.refresh()
        assert result["refreshed"] is True

    def test_comparison_period(self):
        result = self.service.get_comparison(
            "period",
            {"sales": 100},
            {"sales": 80},
        )
        assert "metrics" in result


# --- Time Series Tests ---

class TestTimeSeriesEngine:
    def setup_method(self):
        self.engine = TimeSeriesEngine()

    def test_format_series(self):
        data = [{"label": "Jan", "value": 10}, {"label": "Feb", "value": 20}]
        result = self.engine.format_series("Sales", data)
        assert result["name"] == "Sales"
        assert result["values"] == [10.0, 20.0]

    def test_format_multi_series(self):
        data = [{"label": "Jan", "sales": 10, "orders": 5}]
        configs = [{"name": "Sales", "value_key": "sales"}, {"name": "Orders", "value_key": "orders"}]
        result = self.engine.format_multi_series(configs, data)
        assert len(result) == 2

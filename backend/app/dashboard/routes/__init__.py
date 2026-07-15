"""
AMASCI Dashboard API Routes
===============================
FastAPI endpoints for the Dashboard Intelligence Layer.
"""

import logging
from typing import Any

from fastapi import APIRouter, Query

from app.dashboard.schemas import (
    ComparisonRequest,
    ComparisonResponse,
    DashboardResponse,
    ExecutiveSummaryResponse,
    ExportResponse,
    ForecastDashboardResponse,
    GraphDashboardResponse,
    KPIResponse,
    RCADashboardResponse,
    RiskDashboardResponse,
    TPKEDashboardResponse,
    TrendResponse,
)
from app.dashboard.services import DashboardService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard Intelligence"])

_service: DashboardService | None = None


def _get_service() -> DashboardService:
    global _service
    if _service is None:
        _service = DashboardService()
    return _service


@router.get("", response_model=DashboardResponse)
async def get_dashboard() -> DashboardResponse:
    """Get complete dashboard with KPIs and executive summary."""
    service = _get_service()
    data = service.get_full_dashboard()
    return DashboardResponse(
        kpis=data.get("kpis", {}),
        executive_summary=data.get("executive_summary", {}),
        last_refresh=data.get("last_refresh", ""),
        duration_ms=data.get("duration_ms", 0.0),
        generated_at=data.get("generated_at", ""),
    )


@router.get("/kpis", response_model=KPIResponse)
async def get_kpis() -> KPIResponse:
    """Get all enterprise KPIs."""
    service = _get_service()
    kpis = service.get_kpis()
    return KPIResponse(
        overall_health=kpis.get("overall_health", 0.0),
        supply_chain=kpis.get("supply_chain", {}),
        risk=kpis.get("risk", {}),
        graph=kpis.get("graph", {}),
        tpke=kpis.get("tpke", {}),
        prediction=kpis.get("prediction", {}),
        generated_at=kpis.get("generated_at", ""),
    )


@router.get("/executive-summary", response_model=ExecutiveSummaryResponse)
async def get_executive_summary() -> ExecutiveSummaryResponse:
    """Get executive-level insights and recommendations."""
    service = _get_service()
    summary = service.get_executive_summary()
    return ExecutiveSummaryResponse(
        overall_health=summary.get("overall_health", 0.0),
        health_label=summary.get("health_label", ""),
        top_operational_risks=summary.get("top_operational_risks", []),
        top_suppliers=summary.get("top_suppliers", []),
        critical_warehouses=summary.get("critical_warehouses", []),
        demand_overview=summary.get("demand_overview", {}),
        monthly_highlights=summary.get("monthly_highlights", []),
        system_recommendations=summary.get("system_recommendations", []),
        generated_at=summary.get("generated_at", ""),
    )


@router.get("/forecast", response_model=ForecastDashboardResponse)
async def get_forecast_dashboard() -> ForecastDashboardResponse:
    """Get forecast analytics dashboard."""
    service = _get_service()
    data = service.get_forecast_dashboard()
    return ForecastDashboardResponse(
        cards=data.get("cards", []),
        charts=data.get("charts", []),
        metrics=data.get("metrics", {}),
        history=data.get("history", []),
        generated_at=data.get("generated_at", ""),
    )


@router.get("/risk", response_model=RiskDashboardResponse)
async def get_risk_dashboard() -> RiskDashboardResponse:
    """Get risk analytics dashboard."""
    service = _get_service()
    data = service.get_risk_dashboard()
    return RiskDashboardResponse(
        cards=data.get("cards", []),
        overall_risk=data.get("overall_risk", 0.0),
        overall_level=data.get("overall_level", ""),
        breakdown=data.get("breakdown", []),
        generated_at=data.get("generated_at", ""),
    )


@router.get("/graph", response_model=GraphDashboardResponse)
async def get_graph_dashboard() -> GraphDashboardResponse:
    """Get Knowledge Graph analytics dashboard."""
    service = _get_service()
    data = service.get_graph_dashboard()
    return GraphDashboardResponse(
        cards=data.get("cards", []),
        metrics=data.get("metrics", {}),
        node_distribution=data.get("node_distribution", []),
        relationship_distribution=data.get("relationship_distribution", []),
        generated_at=data.get("generated_at", ""),
    )


@router.get("/tpke", response_model=TPKEDashboardResponse)
async def get_tpke_dashboard() -> TPKEDashboardResponse:
    """Get TPKE evolution analytics dashboard."""
    service = _get_service()
    data = service.get_tpke_dashboard()
    return TPKEDashboardResponse(
        cards=data.get("cards", []),
        metrics=data.get("metrics", {}),
        history=data.get("history", []),
        generated_at=data.get("generated_at", ""),
    )


@router.get("/rootcause", response_model=RCADashboardResponse)
async def get_rca_dashboard() -> RCADashboardResponse:
    """Get Root Cause Analysis analytics dashboard."""
    service = _get_service()
    data = service.get_rca_dashboard()
    return RCADashboardResponse(
        cards=data.get("cards", []),
        metrics=data.get("metrics", {}),
        type_distribution=data.get("type_distribution", []),
        top_root_causes=data.get("top_root_causes", []),
        generated_at=data.get("generated_at", ""),
    )


@router.get("/trends", response_model=TrendResponse)
async def get_trends() -> TrendResponse:
    """Get trend analysis across time granularities."""
    service = _get_service()
    data = service.get_trends()
    return TrendResponse(
        overall_trend=data.get("overall_trend", "stable"),
        daily=data.get("daily", {}),
        weekly=data.get("weekly", {}),
        monthly=data.get("monthly", {}),
        charts=data.get("charts", []),
        generated_at=data.get("generated_at", ""),
    )


@router.post("/comparison", response_model=ComparisonResponse)
async def get_comparison(request: ComparisonRequest) -> ComparisonResponse:
    """Get comparison analytics (period-over-period, prediction vs actual, etc.)."""
    service = _get_service()
    data = service.get_comparison(request.comparison_type, request.current, request.previous)
    return ComparisonResponse(
        comparison_type=data.get("comparison_type", request.comparison_type),
        metrics=data.get("metrics", data),
        generated_at=data.get("generated_at", ""),
    )


@router.get("/export")
async def export_dashboard(
    format_type: str = Query(default="json", description="csv|json|tsv|report|snapshot")
) -> ExportResponse:
    """Export dashboard data in specified format."""
    service = _get_service()
    data = service.export_data(format_type)
    return ExportResponse(
        format=data.get("format", format_type),
        filename=data.get("filename", "export"),
        content=data.get("content", ""),
        generated_at=data.get("generated_at", ""),
    )

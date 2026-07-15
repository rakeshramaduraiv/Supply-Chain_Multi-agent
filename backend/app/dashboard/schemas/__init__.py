"""
AMASCI Dashboard Schemas
===========================
Pydantic models for Dashboard API contracts.
"""

from typing import Any
from pydantic import BaseModel, Field


class DashboardResponse(BaseModel):
    """Full dashboard response."""
    success: bool = True
    kpis: dict[str, Any] = Field(default_factory=dict)
    executive_summary: dict[str, Any] = Field(default_factory=dict)
    last_refresh: str = ""
    duration_ms: float = 0.0
    generated_at: str = ""


class KPIResponse(BaseModel):
    """KPI response."""
    success: bool = True
    overall_health: float = 0.0
    supply_chain: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    graph: dict[str, Any] = Field(default_factory=dict)
    tpke: dict[str, Any] = Field(default_factory=dict)
    prediction: dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""


class ExecutiveSummaryResponse(BaseModel):
    """Executive summary response."""
    success: bool = True
    overall_health: float = 0.0
    health_label: str = ""
    top_operational_risks: list[dict[str, Any]] = Field(default_factory=list)
    top_suppliers: list[dict[str, Any]] = Field(default_factory=list)
    critical_warehouses: list[dict[str, Any]] = Field(default_factory=list)
    demand_overview: dict[str, Any] = Field(default_factory=dict)
    monthly_highlights: list[str] = Field(default_factory=list)
    system_recommendations: list[str] = Field(default_factory=list)
    generated_at: str = ""


class ForecastDashboardResponse(BaseModel):
    """Forecast dashboard response."""
    success: bool = True
    cards: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class RiskDashboardResponse(BaseModel):
    """Risk dashboard response."""
    success: bool = True
    cards: list[dict[str, Any]] = Field(default_factory=list)
    overall_risk: float = 0.0
    overall_level: str = ""
    breakdown: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class GraphDashboardResponse(BaseModel):
    """Graph dashboard response."""
    success: bool = True
    cards: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    node_distribution: list[dict[str, Any]] = Field(default_factory=list)
    relationship_distribution: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class TPKEDashboardResponse(BaseModel):
    """TPKE dashboard response."""
    success: bool = True
    cards: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class RCADashboardResponse(BaseModel):
    """RCA dashboard response."""
    success: bool = True
    cards: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    type_distribution: list[dict[str, Any]] = Field(default_factory=list)
    top_root_causes: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class TrendResponse(BaseModel):
    """Trend analysis response."""
    success: bool = True
    overall_trend: str = "stable"
    daily: dict[str, Any] = Field(default_factory=dict)
    weekly: dict[str, Any] = Field(default_factory=dict)
    monthly: dict[str, Any] = Field(default_factory=dict)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: str = ""


class ComparisonRequest(BaseModel):
    """Comparison request."""
    comparison_type: str = Field(..., description="prediction_vs_actual|period|tpke_impact|graph_versions")
    current: dict[str, Any] = Field(default_factory=dict)
    previous: dict[str, Any] = Field(default_factory=dict)


class ComparisonResponse(BaseModel):
    """Comparison response."""
    success: bool = True
    comparison_type: str = ""
    metrics: dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""


class ExportResponse(BaseModel):
    """Export response."""
    success: bool = True
    format: str = ""
    filename: str = ""
    content: str = ""
    generated_at: str = ""

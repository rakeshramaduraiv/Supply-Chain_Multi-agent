"""
AMASCI Business API Schemas
==============================
Business-friendly request/response models.
All ML/AI internals hidden behind supply chain terminology.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class MonthlyUploadResponse(BaseModel):
    """Response after uploading monthly supply chain data."""
    upload_id: str
    filename: str
    period: str  # e.g. "2024-01"
    records_loaded: int
    columns_detected: int
    data_quality_score: float
    status: str  # "processed", "needs_review"
    processing_time_seconds: float
    warnings: list[str] = []
    uploaded_at: str


class ActualUploadResponse(BaseModel):
    """Response after uploading actual performance data."""
    upload_id: str
    filename: str
    period: str
    records_loaded: int
    records_matched: int
    overall_accuracy: float  # % of forecasts that were correct
    deviation_summary: dict[str, Any]
    status: str
    uploaded_at: str


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class KPICard(BaseModel):
    label: str
    value: str | float
    trend: str  # "up", "down", "stable"
    change_pct: float | None = None
    status: str  # "good", "warning", "critical"


class DashboardResponse(BaseModel):
    """Main dashboard overview for business users."""
    overall_health_score: float
    health_status: str  # "Healthy", "At Risk", "Critical"
    kpis: list[KPICard]
    alerts: list[dict[str, Any]]
    recent_activity: list[str]
    period: str
    last_updated: str


# ─────────────────────────────────────────────────────────────────────────────
# FORECAST SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class ForecastItem(BaseModel):
    entity: str
    entity_type: str  # "Product", "Region", "Supplier"
    period: str
    predicted_risk: str  # "Low", "Medium", "High"
    confidence: float
    factors: list[str]  # Top contributing factors in plain English


class ForecastResponse(BaseModel):
    """Forecast center data for business users."""
    forecast_period: str
    total_predictions: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    overall_confidence: float
    forecasts: list[ForecastItem]
    accuracy_history: list[dict[str, Any]]
    generated_at: str


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH / RELATIONSHIP EXPLORER
# ─────────────────────────────────────────────────────────────────────────────

class RelationshipNode(BaseModel):
    id: str
    label: str
    type: str  # "Supplier", "Product", "Warehouse", etc.
    risk_level: str
    properties: dict[str, Any] = {}


class RelationshipEdge(BaseModel):
    source: str
    target: str
    relationship: str  # "Supplies", "Ships Via", etc.
    strength: float
    is_inferred: bool = False


class GraphResponse(BaseModel):
    """Relationship explorer data for business users."""
    total_entities: int
    total_connections: int
    entity_breakdown: dict[str, int]
    connection_breakdown: dict[str, int]
    top_connected_entities: list[dict[str, Any]]
    risk_clusters: list[dict[str, Any]]
    graph_health: str
    last_updated: str


# ─────────────────────────────────────────────────────────────────────────────
# INTELLIGENCE (GraphRAG)
# ─────────────────────────────────────────────────────────────────────────────

class IntelligenceInsight(BaseModel):
    title: str
    description: str
    severity: str  # "Info", "Warning", "Critical"
    affected_entities: list[str]
    recommended_action: str


class IntelligenceResponse(BaseModel):
    """Supply chain intelligence insights for business users."""
    total_insights: int
    critical_count: int
    warning_count: int
    insights: list[IntelligenceInsight]
    supply_chain_score: float
    risk_trends: list[dict[str, Any]]
    recommendations: list[str]
    generated_at: str


# ─────────────────────────────────────────────────────────────────────────────
# INCIDENT INVESTIGATION (RCA)
# ─────────────────────────────────────────────────────────────────────────────

class IncidentCause(BaseModel):
    entity: str
    entity_type: str
    contribution: float  # 0-100%
    description: str
    path: list[str]  # Causal chain in plain English


class IncidentResponse(BaseModel):
    """Incident investigation results for business users."""
    total_investigations: int
    open_incidents: int
    resolved_incidents: int
    recent_investigations: list[dict[str, Any]]
    top_root_causes: list[dict[str, Any]]
    avg_resolution_time_hours: float
    generated_at: str


# ─────────────────────────────────────────────────────────────────────────────
# BUSINESS ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsResponse(BaseModel):
    """Business analytics overview."""
    delivery_performance: dict[str, Any]
    supplier_performance: list[dict[str, Any]]
    regional_breakdown: list[dict[str, Any]]
    trend_data: list[dict[str, Any]]
    period_comparison: dict[str, Any]
    generated_at: str


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM / ADMINISTRATION
# ─────────────────────────────────────────────────────────────────────────────

class SystemResponse(BaseModel):
    """System status for administrators."""
    system_status: str  # "Operational", "Degraded", "Offline"
    initialized: bool
    last_data_refresh: str | None
    last_analysis_run: str | None
    data_coverage: dict[str, Any]
    component_status: dict[str, str]
    storage_usage: dict[str, Any]
    version: str


# ─────────────────────────────────────────────────────────────────────────────
# ALERT CENTER SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class AlertItem(BaseModel):
    id: str
    name: str
    type: str
    severity: str  # "Critical", "High", "Medium", "Low"
    business_impact: str
    affected_entities: str
    recommendation: str
    forecast_impact: str
    entity_id: str
    entity_type: str
    issue_id: str
    dismissed: bool = False
    created_at: str

class AlertCenterResponse(BaseModel):
    alerts: list[AlertItem]
    total_alerts: int
    critical_alerts: int

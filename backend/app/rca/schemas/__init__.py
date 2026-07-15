"""
AMASCI RCA Schemas
====================
Pydantic models for RCA API request/response contracts.
"""

from typing import Any

from pydantic import BaseModel, Field


# --- Request Schemas ---

class RCAAnalyzeRequest(BaseModel):
    """Request for full RCA analysis."""
    target_id: str = Field(..., description="Node ID of the disrupted entity")
    target_label: str = Field(..., description="Label (Supplier, Product, Warehouse, etc.)")
    rca_type: str = Field(
        ...,
        description="Disruption type: late_delivery|inventory_stress|demand_spike|"
                    "supplier_failure|warehouse_congestion|shipping_delay|customer_complaint",
    )
    max_depth: int = Field(default=3, ge=1, le=5, description="Max traversal depth")
    top_n: int = Field(default=10, ge=1, le=50, description="Top N contributors")


class RCASubgraphRequest(BaseModel):
    """Request for RCA subgraph extraction."""
    target_id: str = Field(..., description="Center node ID")
    target_label: str = Field(..., description="Center node label")
    hops: int = Field(default=2, ge=1, le=4, description="Traversal hops")


class RCAPathRequest(BaseModel):
    """Request for path analysis between two nodes."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")


# --- Response Schemas ---

class RCAReportResponse(BaseModel):
    """Response containing a full RCA report."""
    success: bool = True
    report: dict[str, Any] = Field(default_factory=dict)


class RCASubgraphResponse(BaseModel):
    """Response for RCA subgraph."""
    success: bool = True
    subgraph: dict[str, Any] = Field(default_factory=dict)


class RCAPathResponse(BaseModel):
    """Response for path analysis."""
    success: bool = True
    path: dict[str, Any] = Field(default_factory=dict)


class RCAHistoryResponse(BaseModel):
    """Response for RCA history."""
    success: bool = True
    history: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0


class RCAStatisticsResponse(BaseModel):
    """Response for RCA statistics."""
    success: bool = True
    total_analyses: int = 0
    avg_duration_ms: float = 0.0
    analyses_by_type: dict[str, int] = Field(default_factory=dict)
    total_reports_stored: int = 0


class RCALatestResponse(BaseModel):
    """Response for latest RCA report."""
    success: bool = True
    report: dict[str, Any] | None = None
    error: str | None = None

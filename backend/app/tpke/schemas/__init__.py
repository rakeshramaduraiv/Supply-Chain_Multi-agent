"""
TPKE API Schemas
=================
Request/response models for TPKE endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TPKERunRequest(BaseModel):
    """Request to trigger a TPKE evolution cycle."""
    forecast_run_id: str | None = Field(None, description="Specific forecast run to compare")
    actual_upload_id: str | None = Field(None, description="Specific actual upload to compare")
    triggered_by: str = Field("system", description="User or system identifier")


class TPKEDecayRequest(BaseModel):
    """Request to run edge decay only."""
    reference_time: datetime | None = Field(None, description="Override reference time for decay")


class EdgeMutationResponse(BaseModel):
    action: str
    source: str
    target: str
    relationship_type: str
    weight_before: float | None
    weight_after: float | None
    frequency: int


class PatternResponse(BaseModel):
    source: str
    target: str
    relationship: str
    weight: float
    confidence: float
    frequency: int


class EvolutionReportResponse(BaseModel):
    run_id: str
    timestamp: str
    duration_ms: float
    events_processed: int
    patterns_detected: int
    edges_created: int
    edges_strengthened: int
    edges_decayed: int
    edges_removed: int
    total_tpke_edges: int
    top_patterns: list[PatternResponse]
    parameters: dict[str, Any]


class TPKEStatusResponse(BaseModel):
    total_tpke_edges: int
    active_graph_version: str | int | None = None
    tpke_mutations_on_version: int
    parameters: dict[str, Any]


class TPKEHistoryResponse(BaseModel):
    id: str
    action: str
    source: str
    target: str
    relationship_type: str
    confidence_after: float | None
    created_at: str


class DecayResponse(BaseModel):
    edges_decayed: int
    edges_removed: int
    mutations: list[EdgeMutationResponse]

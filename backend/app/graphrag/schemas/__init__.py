"""
AMASCI GraphRAG Schemas
=========================
Pydantic models for GraphRAG API request/response contracts.
"""

from typing import Any

from pydantic import BaseModel, Field


# --- Request Schemas ---

class ContextRequest(BaseModel):
    """Request for graph context retrieval."""
    entity_id: str = Field(..., description="Node ID of the target entity")
    entity_label: str = Field(..., description="Label of the target entity (Supplier, Product, etc.)")
    context_type: str = Field(
        default="general",
        description="Type of context: general|supplier|product|warehouse|shipment|forecast|risk",
    )
    include_embedding: bool = Field(default=False, description="Include embedding vector in response")


class QueryRequest(BaseModel):
    """Request for natural language or structured query."""
    query: str = Field(..., description="Natural language query or structured query text")


class SubgraphRequest(BaseModel):
    """Request for subgraph extraction."""
    entity_id: str = Field(..., description="Center node ID")
    entity_label: str = Field(..., description="Center node label")
    hops: int = Field(default=2, ge=1, le=3, description="Number of hops (1-3)")


class DependencyRequest(BaseModel):
    """Request for dependency analysis."""
    entity_id: str = Field(..., description="Target entity node ID")
    entity_label: str = Field(..., description="Target entity label")
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum traversal depth")
    include_impact: bool = Field(default=False, description="Include impact propagation analysis")
    initial_risk: float = Field(default=1.0, ge=0.0, le=1.0, description="Initial risk for propagation")


class RootCauseRequest(BaseModel):
    """Request for root cause context."""
    entity_id: str = Field(..., description="Entity experiencing the issue")
    entity_label: str = Field(..., description="Entity label")
    issue_type: str = Field(
        ...,
        description="Issue type: late_delivery|demand_spike|supplier_failure|inventory_stress|shipment_delay",
    )


# --- Response Schemas ---

class ContextResponse(BaseModel):
    """Response containing structured graph context."""
    success: bool = True
    context_type: str
    entity_id: str
    entity_label: str
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    duration_ms: float = 0.0
    generated_at: str = ""


class QueryResponse(BaseModel):
    """Response for query execution with Enterprise GraphRAG schema."""
    success: bool = True
    query: str
    intent: str = ""
    confidence: float = 0.90
    business_explanation: str = ""
    root_cause: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_entities: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_relationships: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    business_recommendation: list[str] = Field(default_factory=list)
    expected_business_impact: str = ""
    answer: str = ""
    validated: bool = True
    resolved_entities: list[str] = Field(default_factory=list)
    cypher: str | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    result_count: int = 0
    chain_output: dict[str, Any] | None = None
    duration_ms: float = 0.0


class SubgraphResponse(BaseModel):
    """Response for subgraph extraction."""
    success: bool = True
    center_id: str
    center_label: str
    center_properties: dict[str, Any] = Field(default_factory=dict)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    hops: int = 1
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    duration_ms: float = 0.0


class DependencyResponse(BaseModel):
    """Response for dependency analysis."""
    success: bool = True
    entity_id: str
    entity_label: str
    ancestors: list[dict[str, Any]] = Field(default_factory=list)
    descendants: list[dict[str, Any]] = Field(default_factory=list)
    critical_dependencies: list[dict[str, Any]] = Field(default_factory=list)
    impact_score: float = 0.0
    dependency_depth: int = 0
    impact_propagation: dict[str, Any] | None = None
    duration_ms: float = 0.0


class HistoryResponse(BaseModel):
    """Response for operation history."""
    success: bool = True
    operations: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0


class StatisticsResponse(BaseModel):
    """Response for service statistics."""
    success: bool = True
    total_operations: int = 0
    cache: dict[str, Any] = Field(default_factory=dict)
    operation_breakdown: dict[str, int] = Field(default_factory=dict)
    repository_metrics: dict[str, Any] = Field(default_factory=dict)


class CacheResponse(BaseModel):
    """Response for cache statistics."""
    success: bool = True
    total_entries: int = 0
    active_entries: int = 0
    expired_entries: int = 0
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    max_size: int = 0
    default_ttl_seconds: float = 0.0

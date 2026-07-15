"""
AMASCI Graph Schemas
======================
Pydantic models for Knowledge Graph API contracts.
"""

from typing import Any

from pydantic import BaseModel, Field


# --- Request Schemas ---

class GraphBuildRequest(BaseModel):
    """Request to build the Knowledge Graph."""
    dataset_version: str = Field(default="", description="Dataset version identifier")
    clear_existing: bool = Field(default=False, description="Clear graph before building")
    order_sample_size: int = Field(default=5000, ge=100, le=50000, description="Max orders to include")


class GraphUpdateRequest(BaseModel):
    """Request for incremental graph update."""
    dataset_version: str = Field(default="", description="Dataset version identifier")


class GraphRebuildRequest(BaseModel):
    """Request for full graph rebuild."""
    dataset_version: str = Field(default="", description="Dataset version identifier")


class GraphImportRequest(BaseModel):
    """Request to import graph data."""
    data: dict[str, Any] = Field(..., description="Exported graph JSON")


class SubgraphRequest(BaseModel):
    """Request for subgraph extraction."""
    node_id: str = Field(..., description="Center node ID")
    max_hops: int = Field(default=2, ge=1, le=5, description="Maximum traversal hops")


class NodeCreateRequest(BaseModel):
    """Request to create a node."""
    label: str = Field(..., description="Node label")
    properties: dict[str, Any] = Field(..., description="Node properties (must include node_id)")


class RelationshipCreateRequest(BaseModel):
    """Request to create a relationship."""
    source_label: str
    source_id: str
    target_label: str
    target_id: str
    rel_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


# --- Response Schemas ---

class BuildResultSchema(BaseModel):
    """Graph build result."""
    nodes_created: int = 0
    relationships_created: int = 0
    nodes_updated: int = 0
    relationships_updated: int = 0
    errors: list[str] = []
    duration_ms: float = 0.0
    graph_version: str = ""
    build_timestamp: str = ""
    dataset_version: str = ""


class GraphStatisticsSchema(BaseModel):
    """Graph statistics response."""
    total_nodes: int = 0
    total_relationships: int = 0
    node_counts: dict[str, int] = {}
    relationship_counts: dict[str, int] = {}
    graph_density: float = 0.0
    connected_components: int = 0


class ValidationIssueSchema(BaseModel):
    """Single validation issue."""
    severity: str
    category: str
    message: str
    details: dict[str, Any] = {}


class ValidationResultSchema(BaseModel):
    """Graph validation result."""
    is_valid: bool = True
    checks_passed: int = 0
    checks_failed: int = 0
    total_checks: int = 0
    issues: list[ValidationIssueSchema] = []


class EntitySchema(BaseModel):
    """Entity with connections."""
    entity: dict[str, Any] | None = None
    connections: list[dict[str, Any]] = []


class SubgraphSchema(BaseModel):
    """Subgraph response."""
    center_node: dict[str, Any] | None = None
    neighbors: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


class NodeListSchema(BaseModel):
    """List of nodes."""
    label: str
    nodes: list[dict[str, Any]] = []
    count: int = 0


class RelationshipListSchema(BaseModel):
    """List of relationships."""
    node_id: str
    relationships: list[dict[str, Any]] = []
    count: int = 0


class GraphVersionSchema(BaseModel):
    """Graph version metadata."""
    version_id: str
    build_timestamp: str
    dataset_version: str
    node_count: int
    relationship_count: int
    build_duration_ms: float
    is_current: bool = True


class CentralitySchema(BaseModel):
    """Centrality analysis result."""
    label: str
    algorithm: str
    results: list[dict[str, Any]] = []

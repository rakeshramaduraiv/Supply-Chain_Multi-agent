"""
AMASCI Knowledge Graph Intelligence Layer
============================================
Static Knowledge Graph construction, management, and analytics for supply chain intelligence.

Modules:
- connection: Neo4j connection manager with pooling and retry
- schema: Constraint and index management (production initialization)
- builder: Bulk graph construction with transaction management
- loader: High-performance batch loader with progress tracking
- extractor: Entity extraction from engineered datasets
- orchestrator: Production pipeline coordinating all graph operations
- versioning: Persistent graph version management (PostgreSQL + Neo4j)
- nodes: Node type definitions and property schemas
- relationships: Relationship type definitions and builders
- analytics: Graph analytics (centrality, PageRank, components)
- validator: Graph integrity validation
- repository: CRUD operations against Neo4j
- services: Business logic orchestration
- schemas: Pydantic API contracts
- routes: FastAPI endpoints
- utils: Shared graph utilities
"""

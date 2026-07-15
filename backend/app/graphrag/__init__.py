"""
AMASCI GraphRAG Intelligence Layer
=====================================
Graph-aware contextual reasoning module.

Architecture:
    GraphContextService (abstraction layer)
        ├── Retrieval Engine (entity, relationship, subgraph)
        ├── Subgraph Engine (configurable hop expansion)
        ├── Dependency Analyzer (ancestor, descendant, impact)
        ├── Context Builder (structured JSON context)
        ├── Embedding Pipeline (node, relationship, subgraph)
        ├── Query Engine (NL → Cypher translation)
        ├── LangChain Integration (prompt templates, chains)
        └── Memory / Cache (TTL-based caching)

The rest of the project MUST interact with this module ONLY through GraphContextService.
LangChain is an internal implementation detail and can be swapped for any other framework.

Usage:
    from app.graphrag.graph_context import GraphContextService

    service = GraphContextService()
    context = await service.get_context(entity_id, entity_label, context_type)
"""

from app.graphrag.graph_context import GraphContextService

__all__ = ["GraphContextService"]

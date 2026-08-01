"""
AMASCI GraphRAG API Routes
=============================
FastAPI endpoints for GraphRAG Intelligence Layer.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.graphrag.schemas import (
    CacheResponse,
    ContextRequest,
    ContextResponse,
    DependencyRequest,
    DependencyResponse,
    HistoryResponse,
    QueryRequest,
    QueryResponse,
    RootCauseRequest,
    StatisticsResponse,
    SubgraphRequest,
    SubgraphResponse,
)
from app.graphrag.services import GraphRAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graphrag", tags=["GraphRAG Intelligence"])

# Service instance (singleton per process)
_service: GraphRAGService | None = None


def _get_service() -> GraphRAGService:
    """Get or create the GraphRAG service singleton."""
    global _service
    if _service is None:
        _service = GraphRAGService()
    return _service


@router.post("/context", response_model=ContextResponse)
async def get_context(request: ContextRequest) -> ContextResponse:
    """
    Retrieve structured graph context for an entity.

    Supports context types: general, supplier, product, warehouse, shipment, forecast, risk.
    """
    service = _get_service()
    try:
        result = await service.get_context(
            entity_id=request.entity_id,
            entity_label=request.entity_label,
            context_type=request.context_type,
            include_embedding=request.include_embedding,
        )
        return ContextResponse(
            context_type=result.get("context_type", request.context_type),
            entity_id=request.entity_id,
            entity_label=request.entity_label,
            context=result.get("context", {}),
            metadata=result.get("metadata", {}),
            embedding=result.get("embedding"),
            duration_ms=result.get("service_duration_ms", result.get("duration_ms", 0)),
            generated_at=result.get("generated_at", ""),
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {e}")
    except Exception as e:
        logger.error(f"Context retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest) -> QueryResponse:
    """
    Execute a natural language query through the 12-stage Enterprise GraphRAG Pipeline.
    """
    service = _get_service()
    try:
        result = await service.execute_query(request.query)
        return QueryResponse(
            query=request.query,
            intent=result.get("intent", "general"),
            confidence=float(result.get("confidence", 0.90)),
            business_explanation=result.get("business_explanation", result.get("answer", "")),
            root_cause=result.get("root_cause", ""),
            evidence=result.get("evidence", []),
            retrieved_entities=result.get("retrieved_entities", []),
            retrieved_relationships=result.get("retrieved_relationships", []),
            recommendations=result.get("recommendations", []),
            business_recommendation=result.get("business_recommendation", []),
            expected_business_impact=result.get("expected_business_impact", ""),
            answer=result.get("answer", ""),
            validated=bool(result.get("validated", True)),
            resolved_entities=[str(e.get("id", "")) for e in result.get("retrieved_entities", []) if "id" in e],
            cypher=result.get("cypher"),
            results=result.get("evidence", []),
            result_count=len(result.get("evidence", [])),
            duration_ms=result.get("service_duration_ms", result.get("duration_ms", 0)),
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {e}")
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subgraph", response_model=SubgraphResponse)
async def get_subgraph(request: SubgraphRequest) -> SubgraphResponse:
    """
    Extract a subgraph around an entity with configurable hop count.

    Returns nodes, edges, and risk summary within the specified neighborhood.
    """
    service = _get_service()
    try:
        result = await service.get_subgraph(
            entity_id=request.entity_id,
            entity_label=request.entity_label,
            hops=request.hops,
        )
        return SubgraphResponse(
            center_id=result.get("center_id", request.entity_id),
            center_label=result.get("center_label", request.entity_label),
            center_properties=result.get("center_properties", {}),
            nodes=result.get("nodes", []),
            edges=result.get("edges", []),
            node_count=result.get("node_count", 0),
            edge_count=result.get("edge_count", 0),
            hops=result.get("hops", request.hops),
            risk_summary=result.get("risk_summary", {}),
            embedding=result.get("embedding"),
            duration_ms=result.get("duration_ms", 0),
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {e}")
    except Exception as e:
        logger.error(f"Subgraph extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dependencies", response_model=DependencyResponse)
async def get_dependencies(request: DependencyRequest) -> DependencyResponse:
    """
    Analyze dependencies for an entity.

    Returns ancestors, descendants, critical dependencies, and impact score.
    """
    service = _get_service()
    try:
        result = await service.get_dependencies(
            entity_id=request.entity_id,
            entity_label=request.entity_label,
            max_depth=request.max_depth,
        )

        impact_propagation = None
        if request.include_impact:
            impact_propagation = await service.get_impact_propagation(
                entity_id=request.entity_id,
                entity_label=request.entity_label,
                initial_risk=request.initial_risk,
            )

        return DependencyResponse(
            entity_id=request.entity_id,
            entity_label=request.entity_label,
            ancestors=result.get("ancestors", []),
            descendants=result.get("descendants", []),
            critical_dependencies=result.get("critical_dependencies", []),
            impact_score=result.get("impact_score", 0.0),
            dependency_depth=result.get("dependency_depth", 0),
            impact_propagation=impact_propagation,
            duration_ms=result.get("duration_ms", 0),
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {e}")
    except Exception as e:
        logger.error(f"Dependency analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/root-cause")
async def get_root_cause_context(request: RootCauseRequest) -> dict[str, Any]:
    """
    Get graph reasoning context for root cause analysis.

    Provides potential causes, risk neighborhood, and issue-specific context.
    Does NOT generate RCA itself - only provides graph reasoning context.
    """
    service = _get_service()
    try:
        result = await service.get_root_cause_context(
            entity_id=request.entity_id,
            entity_label=request.entity_label,
            issue_type=request.issue_type,
        )
        return {"success": True, **result}
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {e}")
    except Exception as e:
        logger.error(f"Root cause context failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=HistoryResponse)
async def get_history(limit: int = Query(default=50, ge=1, le=500)) -> HistoryResponse:
    """Get recent GraphRAG operation history."""
    service = _get_service()
    operations = service.get_history(limit)
    return HistoryResponse(
        operations=operations,
        total_count=len(operations),
    )


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics() -> StatisticsResponse:
    """Get GraphRAG service statistics."""
    service = _get_service()
    stats = service.get_statistics()
    return StatisticsResponse(
        total_operations=stats.get("total_operations", 0),
        cache=stats.get("cache", {}),
        operation_breakdown=stats.get("operation_breakdown", {}),
        repository_metrics=stats.get("repository_metrics", {}),
    )


@router.get("/cache", response_model=CacheResponse)
async def get_cache_statistics() -> CacheResponse:
    """Get cache performance statistics."""
    service = _get_service()
    stats = service.get_cache_statistics()
    return CacheResponse(**stats)


@router.delete("/cache")
async def invalidate_cache(prefix: str | None = Query(default=None)) -> dict[str, Any]:
    """Invalidate cache entries. Optionally filter by prefix."""
    service = _get_service()
    result = service.invalidate_cache(prefix)
    return {"success": True, **result}

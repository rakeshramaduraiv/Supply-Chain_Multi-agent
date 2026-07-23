"""
AMASCI RCA API Routes
========================
FastAPI endpoints for Root Cause Analysis.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.rca.schemas import (
    RCAAnalyzeRequest,
    RCAHistoryResponse,
    RCALatestResponse,
    RCAPathRequest,
    RCAPathResponse,
    RCAReportResponse,
    RCAStatisticsResponse,
    RCASubgraphRequest,
    RCASubgraphResponse,
)
from app.rca.services import RCAService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rca", tags=["Root Cause Analysis"])

_service: RCAService | None = None


def _get_service() -> RCAService:
    """Get or create the RCA service singleton."""
    global _service
    if _service is None:
        _service = RCAService()
    return _service


@router.post("/analyze", response_model=RCAReportResponse)
async def analyze(request: RCAAnalyzeRequest) -> RCAReportResponse:
    """
    Execute full Root Cause Analysis for a supply chain disruption.

    Traverses the knowledge graph, ranks contributing nodes,
    constructs causal chains, and generates a structured report.
    """
    service = _get_service()
    try:
        result = await service.analyze(
            target_id=request.target_id,
            target_label=request.target_label,
            rca_type=request.rca_type,
            max_depth=request.max_depth,
            top_n=request.top_n,
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
        return RCAReportResponse(report=result["report"])
    except ConnectionError as e:
        logger.warning(f"RCA graph unavailable: {e}")
        return RCAReportResponse(report={
            "problem_summary": "Graph database is currently offline. Start Neo4j to enable RCA.",
            "causal_chain": {"events": []},
            "risk_contributors": [],
            "recommended_actions": ["Start the Neo4j database service to enable root cause analysis."],
            "affected_entities": {},
            "overall_confidence": 0.0,
            "critical_relationships": [],
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RCA analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subgraph", response_model=RCASubgraphResponse)
async def get_subgraph(request: RCASubgraphRequest) -> RCASubgraphResponse:
    """
    Extract the RCA-relevant subgraph around a disrupted entity.

    Uses BFS traversal to collect all nodes within the specified hop count.
    """
    service = _get_service()
    try:
        result = await service.get_subgraph(
            target_id=request.target_id,
            target_label=request.target_label,
            hops=request.hops,
        )
        return RCASubgraphResponse(subgraph=result.get("subgraph", {}))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {e}")
    except Exception as e:
        logger.error(f"RCA subgraph extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/path", response_model=RCAPathResponse)
async def get_path(request: RCAPathRequest) -> RCAPathResponse:
    """
    Find the shortest path between two nodes for RCA investigation.

    Returns the path nodes, edges, and hop count.
    """
    service = _get_service()
    try:
        result = await service.get_path(
            source_id=request.source_id,
            target_id=request.target_id,
        )
        return RCAPathResponse(path=result.get("path", {}))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Graph database unavailable: {e}")
    except Exception as e:
        logger.error(f"RCA path analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=RCAHistoryResponse)
async def get_history(limit: int = Query(default=50, ge=1, le=500)) -> RCAHistoryResponse:
    """Get RCA analysis history."""
    service = _get_service()
    history = service.get_history(limit)
    return RCAHistoryResponse(history=history, total_count=len(history))


@router.get("/statistics", response_model=RCAStatisticsResponse)
async def get_statistics() -> RCAStatisticsResponse:
    """Get RCA service statistics."""
    service = _get_service()
    stats = service.get_statistics()
    return RCAStatisticsResponse(
        total_analyses=stats.get("total_analyses", 0),
        avg_duration_ms=stats.get("avg_duration_ms", 0.0),
        analyses_by_type=stats.get("analyses_by_type", {}),
        total_reports_stored=stats.get("total_reports_stored", 0),
    )


@router.get("/latest", response_model=RCALatestResponse)
async def get_latest() -> RCALatestResponse:
    """Get the most recent RCA report."""
    service = _get_service()
    result = service.get_latest()
    if not result.get("success"):
        return RCALatestResponse(success=False, error=result.get("error"))
    return RCALatestResponse(report=result.get("report"))

"""
AMASCI Context Builder REST API Routes
=======================================
Endpoints for building and retrieving unified business context synthesized across 7 platform modules.
Mediates LLM data isolation — the LLM never accesses Neo4j directly.
"""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Body

from app.graphrag.context_builder.service import ContextBuilderService
from app.schemas import BaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/context-builder", tags=["Context Builder"])

_service: ContextBuilderService | None = None


def _get_context_service() -> ContextBuilderService:
    global _service
    if _service is None:
        _service = ContextBuilderService()
    return _service


@router.get("/build", response_model=BaseResponse[dict[str, Any]])
async def build_context_get(
    entity_id: str = Query(default="SUP_001", description="Entity node ID"),
    entity_label: str = Query(default="Supplier", description="Entity node label"),
    query: str = Query(default="", description="Optional user question"),
) -> BaseResponse[dict[str, Any]]:
    """Build unified context synthesizing all 7 platform modules (GET)."""
    try:
        service = _get_context_service()
        payload = await service.build_unified_context(entity_id=entity_id, entity_label=entity_label, query=query)
        return BaseResponse(
            success=True,
            message=f"Unified context built successfully for {entity_label}/{entity_id}",
            data=payload.to_dict(),
        )
    except Exception as e:
        logger.error(f"Context builder failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build", response_model=BaseResponse[dict[str, Any]])
async def build_context_post(
    payload_in: dict[str, Any] = Body(...),
) -> BaseResponse[dict[str, Any]]:
    """Build unified context synthesizing all 7 platform modules (POST)."""
    entity_id = payload_in.get("entity_id", "SUP_001")
    entity_label = payload_in.get("entity_label", "Supplier")
    query = payload_in.get("query", "")
    try:
        service = _get_context_service()
        payload = await service.build_unified_context(entity_id=entity_id, entity_label=entity_label, query=query)
        return BaseResponse(
            success=True,
            message=f"Unified context built successfully for {entity_label}/{entity_id}",
            data=payload.to_dict(),
        )
    except Exception as e:
        logger.error(f"Context builder failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

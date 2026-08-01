"""
AMASCI Agent Memory REST API Routes
====================================
Exposes endpoints for querying ML Agent prediction and decision history records.
"""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Path

from app.ml.agent_memory import get_agent_memory
from app.schemas import BaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent-memory", tags=["Agent Memory"])


@router.get("/history/{agent}", response_model=BaseResponse[list[dict[str, Any]]])
async def get_agent_history(
    agent: str = Path(..., description="Agent name: demand, supplier, inventory, logistics"),
    limit: int = Query(default=50, ge=1, le=500),
) -> BaseResponse[list[dict[str, Any]]]:
    """Retrieve prediction and decision history for a specific ML agent."""
    try:
        mem = get_agent_memory()
        history = mem.get_history(agent=agent, limit=limit)
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(history)} memory records for agent '{agent}'",
            data=history,
        )
    except Exception as e:
        logger.error(f"Failed to fetch agent memory history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{agent}", response_model=BaseResponse[dict[str, Any]])
async def get_agent_stats(
    agent: str = Path(..., description="Agent name: demand, supplier, inventory, logistics"),
) -> BaseResponse[dict[str, Any]]:
    """Retrieve accuracy and confidence summary statistics for an ML agent."""
    try:
        mem = get_agent_memory()
        stats = mem.get_stats(agent=agent)
        return BaseResponse(
            success=True,
            message=f"Retrieved memory stats for agent '{agent}'",
            data=stats,
        )
    except Exception as e:
        logger.error(f"Failed to fetch agent memory stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records", response_model=BaseResponse[list[dict[str, Any]]])
async def get_all_records(
    entity_id: str | None = Query(default=None, description="Optional entity ID filter"),
    limit: int = Query(default=50, ge=1, le=500),
) -> BaseResponse[list[dict[str, Any]]]:
    """Query memory records across all agents."""
    try:
        mem = get_agent_memory()
        records = mem.query_memory(entity_id=entity_id, limit=limit)
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(records)} memory records across all agents",
            data=[r.to_dict() for r in records],
        )
    except Exception as e:
        logger.error(f"Failed to query agent memory records: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

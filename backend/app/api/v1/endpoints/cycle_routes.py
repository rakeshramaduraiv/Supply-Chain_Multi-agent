"""
app/api/v1/endpoints/cycle_routes.py
=====================================
Resync endpoint for clients that connect late or drop during a cycle.

GET /api/v1/cycle/{cycle_id}/stages
    Returns every event (RUNNING + COMPLETED/SKIPPED/FAILED + cycle.complete)
    recorded for the given cycle_id, in emission order.
"""

from fastapi import APIRouter, HTTPException
from typing import Any

from app.services.cycle_store import get_events

router = APIRouter(prefix="/cycle", tags=["Cycle"])


@router.get("/{cycle_id}/stages", response_model=list[dict[str, Any]])
async def get_cycle_stages(cycle_id: str):
    """
    Return all stage events recorded for *cycle_id*.

    Clients that miss WebSocket events during a cycle can call this endpoint
    to reconstruct the full stage timeline.  Events are in emission order:
    RUNNING sentinel → COMPLETED/SKIPPED/FAILED result → … → cycle.complete.

    404 if the cycle_id is unknown or has been evicted from the in-process store.
    """
    events = get_events(cycle_id)
    if events is None:
        raise HTTPException(
            status_code=404,
            detail=f"cycle_id {cycle_id!r} not found. "
                   "It may have been evicted (only the last 20 cycles are kept).",
        )
    return events

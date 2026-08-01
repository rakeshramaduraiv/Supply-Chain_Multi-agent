"""
AMASCI Agent Coordinator Summary Endpoints
===========================================
Exposes REST APIs to retrieve active coordinator execution state, communication logs,
resolved prediction conflicts, and arbitrated agent payloads.
"""

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.ml.prediction.collaborative_pipeline import get_agent_coordinator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/coordinator", tags=["Agent Coordinator"])


@router.get("/summary")
async def get_coordinator_summary() -> dict[str, Any]:
    """Retrieve active Coordinator execution summary, communication logs, and agent payloads."""
    coordinator = get_agent_coordinator()
    if coordinator.latest_summary:
        return coordinator.latest_summary.to_dict()

    # Execute default cycle if no summary exists
    try:
        dummy_df = pd.DataFrame([{"Sales": 500.0, "Order Item Quantity": 2}])
        res = coordinator.execute_coordinated_pipeline(dummy_df)
        return res.to_dict()
    except Exception as e:
        logger.error(f"Coordinator execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

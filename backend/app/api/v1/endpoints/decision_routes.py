"""
AMASCI Decision Intelligence REST API Routes
==============================================
Exposes endpoints for computing deterministic business decisions based on LLM outputs,
multi-agent risk predictions, graph evidence, and business constraints.
"""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Body

from app.engine.decision_engine import DecisionEngine
from app.schemas import BaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/decision", tags=["Decision Intelligence"])
_engine = DecisionEngine()


@router.post("/evaluate", response_model=BaseResponse[dict[str, Any]])
async def evaluate_decision(
    payload_in: dict[str, Any] = Body(...),
) -> BaseResponse[dict[str, Any]]:
    """Compute business decision metrics (priority, severity, cost, savings, action)."""
    agent_outputs = payload_in.get("agent_outputs", {})
    business_rules = payload_in.get("business_rules", [])
    try:
        decision = _engine.compute_decision(agent_outputs=agent_outputs, business_rules=business_rules)
        return BaseResponse(
            success=True,
            message="Computed Decision Intelligence Output successfully",
            data=decision.to_dict(),
        )
    except Exception as e:
        logger.error(f"Decision evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

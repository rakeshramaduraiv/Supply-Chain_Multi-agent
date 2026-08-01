"""
AMASCI Prediction Integration API Routes
=========================================
Endpoints for querying stored predictions and prediction histories on Neo4j nodes.
"""

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Path

from app.graph.prediction_integration import PredictionIntegrationLayer, auto_sync_predictions
from app.schemas import BaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["Prediction Integration"])


@router.get("/latest/{label}/{node_id}", response_model=BaseResponse[dict[str, Any]])
async def get_latest_prediction(
    label: str = Path(..., description="Node label: Supplier, Warehouse, Product, Shipment"),
    node_id: str = Path(..., description="Unique node ID"),
) -> BaseResponse[dict[str, Any]]:
    """Retrieve the latest stored multi-agent predictions for a specific node."""
    try:
        pil = PredictionIntegrationLayer()
        result = await pil.get_latest_prediction(label=label, node_id=node_id)
        if not result:
            return BaseResponse(
                success=False,
                message=f"No predictions found for {label}/{node_id}",
                data={"node_id": node_id, "label": label, "has_predictions": False},
            )
        return BaseResponse(
            success=True,
            message=f"Retrieved latest predictions for {label}/{node_id}",
            data=result,
        )
    except Exception as e:
        logger.error(f"Failed to fetch latest prediction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch latest prediction: {str(e)}")


@router.get("/history/{label}/{node_id}", response_model=BaseResponse[list[dict[str, Any]]])
async def get_prediction_history(
    label: str = Path(..., description="Node label: Supplier, Warehouse, Product, Shipment"),
    node_id: str = Path(..., description="Unique node ID"),
) -> BaseResponse[list[dict[str, Any]]]:
    """Retrieve the prediction history log for a specific node."""
    try:
        pil = PredictionIntegrationLayer()
        history = await pil.get_prediction_history(label=label, node_id=node_id)
        return BaseResponse(
            success=True,
            message=f"Retrieved {len(history)} historical prediction entries for {label}/{node_id}",
            data=history,
        )
    except Exception as e:
        logger.error(f"Failed to fetch prediction history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch prediction history: {str(e)}")


@router.post("/sync", response_model=BaseResponse[dict[str, Any]])
async def sync_predictions() -> BaseResponse[dict[str, Any]]:
    """Manually trigger prediction writeback to Neo4j nodes."""
    try:
        res = await auto_sync_predictions()
        return BaseResponse(
            success=True,
            message="Multi-Agent predictions synced to Neo4j",
            data=res,
        )
    except Exception as e:
        logger.error(f"Prediction sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction sync failed: {str(e)}")

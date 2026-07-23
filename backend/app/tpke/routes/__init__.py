"""
TPKE API Routes
================
Endpoints for Temporal Pattern-Triggered Knowledge Graph Evolution.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import get_db_session
from app.graph.connection import get_connection_manager
from app.repositories.domain import ForecastRunRepository, ForecastResultRepository, ActualUploadRepository
from app.services.domain.tpke_service import TPKELogService
from app.tpke.engine import TPKEEngine
from app.api.v1.endpoints.ws import broadcast_event
from app.tpke.schemas import (
    DecayResponse,
    EdgeMutationResponse,
    EvolutionReportResponse,
    TPKEDecayRequest,
    TPKEHistoryResponse,
    TPKERunRequest,
    TPKEStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tpke", tags=["TPKE"])


@router.post("/evolve", response_model=EvolutionReportResponse)
async def run_evolution(
    request: TPKERunRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Trigger a TPKE evolution cycle.

    Compares forecast predictions against actual uploads,
    detects temporal patterns, and evolves the knowledge graph.
    """
    conn = get_connection_manager()

    # Load forecast data
    forecast_repo = ForecastRunRepository(session)
    result_repo = ForecastResultRepository(session)

    if request.forecast_run_id:
        run = await forecast_repo.get_by_id(request.forecast_run_id)
        if not run:
            raise HTTPException(404, "Forecast run not found")
    else:
        run = await forecast_repo.get_latest()
        if not run:
            raise HTTPException(404, "No forecast runs available")

    results = await result_repo.get_by_run(run.id)
    forecast_data = [
        {
            "entity_id": r.entity_id,
            "entity_type": r.entity_type,
            "predicted_value": r.predicted_value,
            "forecast_date": r.forecast_date.isoformat() if r.forecast_date else "",
            "metadata": r.metadata_json or {},
        }
        for r in results
    ]

    # Load actual data
    actual_repo = ActualUploadRepository(session)

    if request.actual_upload_id:
        upload = await actual_repo.get_by_id(request.actual_upload_id)
        if not upload:
            raise HTTPException(404, "Actual upload not found")
        uploads = [upload]
    else:
        uploads = await actual_repo.get_by_status("compared")
        if not uploads:
            raise HTTPException(404, "No compared actual uploads available")

    # Extract actual records from comparison_json
    actual_data = []
    for upload in uploads:
        comparison = upload.comparison_json or {}
        records = comparison.get("records", [])
        for rec in records:
            actual_data.append({
                "entity_id": rec.get("entity_id", ""),
                "entity_type": rec.get("entity_type", ""),
                "actual_value": rec.get("actual_value", 0),
                "date": rec.get("date", ""),
            })

    if not actual_data:
        raise HTTPException(400, "No actual comparison records found")

    # Run TPKE engine
    engine = TPKEEngine(conn, session)
    report = await engine.run(
        forecast_data=forecast_data,
        actual_data=actual_data,
        triggered_by=request.triggered_by,
    )

    await broadcast_event("TPKE Completed", {"forecast_run_id": run.id})

    return report.to_dict()


@router.post("/decay", response_model=DecayResponse)
async def run_decay(
    request: TPKEDecayRequest = TPKEDecayRequest(),
    session: AsyncSession = Depends(get_db_session),
):
    """Run edge decay pass on all TPKE-inferred edges."""
    conn = get_connection_manager()
    engine = TPKEEngine(conn, session)
    result = await engine.run_decay_only()

    await broadcast_event("TPKE Completed", {"action": "decay"})

    return {
        "edges_decayed": result.edges_decayed,
        "edges_removed": result.edges_removed,
        "mutations": [
            {
                "action": m.action,
                "source": f"{m.source_type}:{m.source_id}",
                "target": f"{m.target_type}:{m.target_id}",
                "relationship_type": m.relationship_type,
                "weight_before": m.weight_before,
                "weight_after": m.weight_after,
                "frequency": m.frequency,
            }
            for m in result.mutations
        ],
    }


@router.get("/status", response_model=TPKEStatusResponse)
async def get_status(session: AsyncSession = Depends(get_db_session)):
    """Get current TPKE engine status and parameters."""
    conn = get_connection_manager()
    engine = TPKEEngine(conn, session)
    return await engine.get_status()


@router.get("/history", response_model=list[TPKEHistoryResponse])
async def get_history(
    days: int = 30,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """Get TPKE mutation history."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    service = TPKELogService(session)
    mutations = await service.get_recent_mutations(since, limit)
    return mutations


@router.get("/edges")
async def get_tpke_edges(session: AsyncSession = Depends(get_db_session)):
    """Get all current TPKE-inferred edges from Neo4j."""
    try:
        conn = get_connection_manager()
        from app.tpke.edge_manager import EdgeManager
        manager = EdgeManager(conn, session)
        edges = await manager.get_all_edges()
        return {"count": len(edges), "edges": edges}
    except Exception as e:
        logger.warning(f"TPKE edges unavailable (Neo4j offline?): {e}")
        return {"count": 0, "edges": []}


@router.get("/summary")
async def get_summary(session: AsyncSession = Depends(get_db_session)):
    """Get TPKE action summary (counts by action type)."""
    service = TPKELogService(session)
    return await service.get_action_summary()

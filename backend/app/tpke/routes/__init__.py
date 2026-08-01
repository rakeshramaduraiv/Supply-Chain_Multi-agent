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


@router.get("/status")
async def get_status(session: AsyncSession = Depends(get_db_session)):
    """Get current TPKE engine status and parameters."""
    try:
        conn = get_connection_manager()
        engine = TPKEEngine(conn, session)
        return await engine.get_status()
    except Exception as e:
        logger.warning(f"TPKE status route error: {e}")
        return {
            "total_tpke_edges": 0,
            "active_graph_version": "v1.0",
            "tpke_mutations_on_version": 0,
            "parameters": {
                "window_size_days": 90,
                "frequency_threshold_K": 20,
                "confidence_threshold_theta": 0.80,
                "decay_rate": 0.05,
            },
        }


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


@router.get("/evolution-stats")
async def get_evolution_stats(session: AsyncSession = Depends(get_db_session)):
    """Get TPKE evolution statistics: new edges, removed edges, decay pass status."""
    try:
        service = TPKELogService(session)
        summary = await service.get_action_summary()
        conn = get_connection_manager()
        res = await conn.execute_query("MATCH ()-[r:TPKE_INFERRED]->() RETURN count(r) AS total, avg(r.weight) AS avg_weight")
        row = res[0] if res else {}
        return {
            "total_tpke_edges": row.get("total", 0),
            "average_edge_weight": round(row.get("avg_weight", 0.8) or 0.8, 4),
            "mutations_summary": summary,
            "status": "active"
        }
    except Exception as e:
        logger.warning(f"Evolution stats error: {e}")
        return {"total_tpke_edges": 0, "average_edge_weight": 0.0, "status": "offline"}


@router.get("/evolving-relationships")
async def get_evolving_relationships(limit: int = 10):
    """Get top evolving graph relationships ranked by weight/frequency."""
    try:
        conn = get_connection_manager()
        cypher = """
            MATCH (s)-[r:TPKE_INFERRED]->(t)
            RETURN s.entity_id AS source_id, labels(s)[0] AS source_type,
                   t.entity_id AS target_id, labels(t)[0] AS target_type,
                   r.relationship_type AS rel_type, r.weight AS weight,
                   r.frequency AS frequency, r.is_stable AS is_stable
            ORDER BY r.weight DESC LIMIT $limit
        """
        records = await conn.execute_query(cypher, {"limit": limit})
        return {"count": len(records), "relationships": records}
    except Exception as e:
        logger.warning(f"Evolving relationships error: {e}")
        return {"count": 0, "relationships": []}


@router.get("/predictions-history")
async def get_predictions_history(limit: int = 20):
    """Get graph prediction history stored on entity nodes."""
    try:
        conn = get_connection_manager()
        cypher = """
            MATCH (n) WHERE n.prediction_timestamp IS NOT NULL
            RETURN n.node_id AS node_id, labels(n)[0] AS label,
                   n.risk_score AS risk_score, n.inventory_risk AS inventory_risk,
                   n.forecast_quantity AS forecast_quantity,
                   n.prediction_confidence AS confidence,
                   n.prediction_timestamp AS timestamp
            ORDER BY n.prediction_timestamp DESC LIMIT $limit
        """
        records = await conn.execute_query(cypher, {"limit": limit})
        return {"count": len(records), "predictions": records}
    except Exception as e:
        logger.warning(f"Predictions history error: {e}")
        return {"count": 0, "predictions": []}


@router.get("/graph-version")
async def get_graph_version(session: AsyncSession = Depends(get_db_session)):
    """Get graph versioning metadata and mutation counters."""
    try:
        conn = get_connection_manager()
        from app.graph.versioning import GraphVersionManager
        vm = GraphVersionManager(conn, session)
        version = await vm.get_current_version()
        return version.to_dict() if hasattr(version, "to_dict") else {"version_id": "v1.0", "status": "active"}
    except Exception as e:
        logger.warning(f"Graph version error: {e}")
        return {"version_id": "v1.0", "status": "active", "error": str(e)}


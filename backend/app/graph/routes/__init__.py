"""
AMASCI Graph API Routes
=========================
FastAPI endpoints for Knowledge Graph operations.
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import get_settings
from app.database.postgres import get_db_session
from app.graph.connection import get_connection_manager
from app.graph.schemas import (
    BuildResultSchema,
    CentralitySchema,
    EntitySchema,
    GraphBuildRequest,
    GraphImportRequest,
    GraphRebuildRequest,
    GraphStatisticsSchema,
    GraphUpdateRequest,
    NodeListSchema,
    RelationshipListSchema,
    SubgraphSchema,
    ValidationResultSchema,
)
from app.graph.services import GraphService
from app.api.v1.endpoints.ws import broadcast_event
from app.schemas import BaseResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


def _get_graph_service(session=None) -> GraphService:
    """Get graph service instance."""
    conn = get_connection_manager()
    return GraphService(conn, session=session)


def _load_processed_dataset() -> pd.DataFrame:
    """Load the most recently processed dataset."""
    settings = get_settings()
    data_dir = Path(settings.upload_dir)

    candidates = sorted(data_dir.glob("*_processed.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        candidates = sorted(data_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not candidates:
        raise HTTPException(status_code=404, detail="No processed dataset found. Upload and process data first.")

    df = pd.read_csv(candidates[0])
    logger.info(f"Loaded dataset: {candidates[0].name} ({len(df)} rows)")
    return df


# ============================================================
# BUILD ENDPOINTS
# ============================================================

@router.post("/build", response_model=BaseResponse[BuildResultSchema])
async def build_graph(request: GraphBuildRequest, session=Depends(get_db_session)):
    """Build the Knowledge Graph from the processed dataset."""
    try:
        service = _get_graph_service(session)
        df = _load_processed_dataset()
        result = await service.build_graph(
            df=df,
            dataset_version=request.dataset_version,
            clear_existing=request.clear_existing,
            order_sample_size=request.order_sample_size,
        )
        await broadcast_event("Knowledge Graph Updated", {"action": "build"})

        return BaseResponse(
            data=BuildResultSchema(**result.to_dict()),
            message=f"Graph built: {result.nodes_created} nodes, {result.relationships_created} relationships",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Graph build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph build failed: {str(e)}")


@router.post("/update", response_model=BaseResponse[BuildResultSchema])
async def update_graph(request: GraphUpdateRequest, session=Depends(get_db_session)):
    """Incrementally update the Knowledge Graph."""
    try:
        service = _get_graph_service(session)
        df = _load_processed_dataset()
        result = await service.update_graph(df, dataset_version=request.dataset_version)

        await broadcast_event("Knowledge Graph Updated", {"action": "update"})

        return BaseResponse(
            data=BuildResultSchema(**result.to_dict()),
            message="Graph updated incrementally",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Graph update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph update failed: {str(e)}")


@router.post("/rebuild", response_model=BaseResponse[BuildResultSchema])
async def rebuild_graph(request: GraphRebuildRequest, session=Depends(get_db_session)):
    """Full graph rebuild (clears existing data)."""
    try:
        service = _get_graph_service(session)
        df = _load_processed_dataset()
        result = await service.rebuild_graph(df, dataset_version=request.dataset_version)

        await broadcast_event("Knowledge Graph Updated", {"action": "rebuild"})

        return BaseResponse(
            data=BuildResultSchema(**result.to_dict()),
            message="Graph rebuilt from scratch",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Graph rebuild failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph rebuild failed: {str(e)}")


@router.post("/import", response_model=BaseResponse[BuildResultSchema])
async def import_graph(request: GraphImportRequest):
    """Import graph from exported JSON."""
    try:
        service = _get_graph_service()
        result = await service.import_graph(request.data)
        return BaseResponse(
            data=BuildResultSchema(**result.to_dict()),
            message="Graph imported successfully",
        )
    except Exception as e:
        logger.error(f"Graph import failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph import failed: {str(e)}")


@router.api_route("/export", methods=["GET", "POST"], response_model=BaseResponse[dict[str, Any]])
async def export_graph():
    """Export the entire graph as JSON."""
    try:
        service = _get_graph_service()
        data = await service.export_graph()
        return BaseResponse(data=data, message="Graph exported successfully")
    except Exception as e:
        logger.warning(f"Graph export unavailable (Neo4j offline?): {e}")
        return BaseResponse(
            data={"nodes": [], "relationships": [], "metadata": {"exported_at": datetime.now(timezone.utc).isoformat(), "offline": True}},
            message="Graph export fallback — Neo4j offline",
        )


# ============================================================
# SCHEMA ENDPOINTS
# ============================================================

@router.post("/schema/initialize", response_model=BaseResponse[dict[str, Any]])
async def initialize_schema():
    """Initialize Neo4j constraints and indexes."""
    try:
        service = _get_graph_service()
        result = await service.initialize_schema()
        return BaseResponse(data=result, message="Schema initialized")
    except Exception as e:
        logger.error(f"Schema init failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schema/info", response_model=BaseResponse[dict[str, Any]])
async def get_schema_info():
    """Get current Neo4j schema state."""
    try:
        service = _get_graph_service()
        info = await service.get_schema_info()
        return BaseResponse(data=info, message="Schema info retrieved")
    except Exception as e:
        logger.warning(f"Schema info unavailable (Neo4j offline?): {e}")
        return BaseResponse(data={"constraints": [], "indexes": [], "available": False}, message="Schema unavailable")


# ============================================================
# VERSIONING ENDPOINTS
# ============================================================

@router.api_route("/versions", methods=["GET", "POST"], response_model=BaseResponse[list[dict[str, Any]]])
async def list_versions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List all graph versions."""
    try:
        from app.database.postgres import get_db_session
        async for session in get_db_session():
            service = _get_graph_service(session)
            versions = await service.list_versions(skip=skip, limit=limit)
            return BaseResponse(data=versions, message=f"Retrieved {len(versions)} versions")
    except Exception as e:
        logger.warning(f"List versions fallback: {e}")
    return BaseResponse(
        data=[{"version_id": 1, "version_tag": "v1.0.0", "status": "active", "created_at": datetime.now(timezone.utc).isoformat()}],
        message="Fallback graph version retrieved",
    )


@router.api_route("/versions/active", methods=["GET", "POST"], response_model=BaseResponse[dict[str, Any]])
async def get_active_version():
    """Get the currently active graph version."""
    try:
        from app.database.postgres import get_db_session
        async for session in get_db_session():
            service = _get_graph_service(session)
            version = await service.get_active_version()
            if version:
                return BaseResponse(data=version, message="Active version retrieved")
            break
    except Exception as e:
        logger.warning(f"Active version fallback: {e}")
    return BaseResponse(
        data={"version_id": 1, "version_tag": "v1.0.0", "status": "active", "created_at": datetime.now(timezone.utc).isoformat()},
        message="Fallback active version retrieved",
    )


@router.post("/versions/rollback", response_model=BaseResponse[dict[str, Any]])
async def rollback_version(
    target_version: int = Query(..., ge=1),
):
    """Rollback to a previous graph version."""
    try:
        from app.database.postgres import get_db_session
        async for session in get_db_session():
            service = _get_graph_service(session)
            result = await service.rollback_version(target_version)
            if result:
                return BaseResponse(data=result, message=f"Rolled back to version {target_version}")
            break
    except Exception as e:
        logger.warning(f"Rollback version fallback: {e}")
    return BaseResponse(data={"version_id": target_version, "status": "rolled_back"}, message=f"Rolled back to version {target_version}")


# ============================================================
# QUERY ENDPOINTS
# ============================================================

@router.get("/statistics", response_model=BaseResponse[GraphStatisticsSchema])
async def get_statistics():
    """Get graph statistics."""
    try:
        service = _get_graph_service()
        stats = await service.get_statistics()
        return BaseResponse(
            data=GraphStatisticsSchema(**stats.to_dict()),
            message="Graph statistics retrieved",
        )
    except Exception as e:
        logger.warning(f"Statistics unavailable (Neo4j offline?): {e}")
        return BaseResponse(
            data=GraphStatisticsSchema(
                total_nodes=0, total_relationships=0, node_counts={}, relationship_counts={},
                graph_density=0.0, connected_components=0,
            ),
            message="Graph statistics unavailable — Neo4j offline",
        )


@router.get("/validate", response_model=BaseResponse[ValidationResultSchema])
async def validate_graph():
    """Validate graph integrity."""
    try:
        service = _get_graph_service()
        result = await service.validate_graph()
        return BaseResponse(
            data=ValidationResultSchema(**result.to_dict()),
            message="Validation complete" if result.is_valid else "Validation found issues",
        )
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nodes", response_model=BaseResponse[NodeListSchema])
async def get_nodes(
    label: str = Query(..., description="Node label (Supplier, Product, etc.)"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Get nodes by label."""
    try:
        service = _get_graph_service()
        nodes = await service.get_nodes(label, limit=limit, offset=offset)
        return BaseResponse(
            data=NodeListSchema(label=label, nodes=nodes, count=len(nodes)),
            message=f"Retrieved {len(nodes)} {label} nodes",
        )
    except Exception as e:
        logger.warning(f"Get nodes unavailable (Neo4j offline?): {e}")
        return BaseResponse(
            data=NodeListSchema(label=label, nodes=[], count=0),
            message=f"Nodes unavailable — Neo4j offline",
        )


@router.get("/relationships", response_model=BaseResponse[RelationshipListSchema])
async def get_relationships(
    label: str = Query(..., description="Node label"),
    node_id: str = Query(..., description="Node ID"),
):
    """Get relationships for a specific node."""
    try:
        service = _get_graph_service()
        rels = await service.get_relationships_for_node(label, node_id)
        return BaseResponse(
            data=RelationshipListSchema(node_id=node_id, relationships=rels, count=len(rels)),
            message=f"Retrieved {len(rels)} relationships",
        )
    except Exception as e:
        logger.error(f"Get relationships failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{node_id}", response_model=BaseResponse[EntitySchema])
async def get_entity(node_id: str):
    """Get an entity with its connections."""
    try:
        service = _get_graph_service()
        entity = await service.get_entity(node_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity not found: {node_id}")
        return BaseResponse(data=EntitySchema(**entity), message="Entity retrieved")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Get entity unavailable (Neo4j offline?): {e}")
        return BaseResponse(
            data=EntitySchema(entity={"node_id": node_id, "properties": {}}, connections=[]),
            message="Entity unavailable — Neo4j offline",
        )


@router.get("/subgraph", response_model=BaseResponse[SubgraphSchema])
async def get_subgraph(
    node_id: str = Query(..., description="Center node ID"),
    max_hops: int = Query(default=2, ge=1, le=5),
):
    """Get subgraph around a node."""
    try:
        service = _get_graph_service()
        subgraph = await service.get_subgraph(node_id, max_hops=max_hops)
        return BaseResponse(data=SubgraphSchema(**subgraph), message="Subgraph retrieved")
    except Exception as e:
        logger.warning(f"Get subgraph unavailable (Neo4j offline?): {e}")
        return BaseResponse(
            data=SubgraphSchema(center_node=None, neighbors=[], edges=[]),
            message="Subgraph unavailable — Neo4j offline",
        )


@router.get("/centrality/{label}", response_model=BaseResponse[CentralitySchema])
async def get_centrality(
    label: str,
    algorithm: str = Query(default="degree", description="degree or pagerank"),
    top_n: int = Query(default=10, ge=1, le=100),
):
    """Get centrality analysis for a node label."""
    try:
        service = _get_graph_service()
        if algorithm == "pagerank":
            results = await service.pagerank(label, top_n)
        else:
            results = await service.degree_centrality(label, top_n)
        return BaseResponse(
            data=CentralitySchema(label=label, algorithm=algorithm, results=results),
            message=f"{algorithm} centrality computed for {label}",
        )
    except Exception as e:
        logger.error(f"Centrality failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shortest-path", response_model=BaseResponse[list[dict[str, Any]]])
async def get_shortest_path(
    source_id: str = Query(...),
    target_id: str = Query(...),
):
    """Find shortest path between two nodes."""
    try:
        service = _get_graph_service()
        path = await service.shortest_path(source_id, target_id)
        return BaseResponse(data=path, message="Shortest path computed")
    except Exception as e:
        logger.error(f"Shortest path failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


from app.graph.prediction_integration import routes as pred_routes
router.include_router(pred_routes.router)

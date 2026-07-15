"""
AMASCI Health Check Endpoints
===============================
System health, readiness, and liveness probes.
"""

import logging

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas import HealthResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health Check",
)
async def health_check() -> HealthResponse:
    """Check overall system health including all dependencies."""
    services = {}

    # Check PostgreSQL
    try:
        from app.database.postgres import engine
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        services["postgresql"] = "healthy"
    except Exception:
        services["postgresql"] = "unhealthy"

    # Check Neo4j
    try:
        from app.database.neo4j import get_neo4j_session
        async with get_neo4j_session() as session:
            await session.run("RETURN 1")
        services["neo4j"] = "healthy"
    except Exception:
        services["neo4j"] = "unhealthy"

    overall_status = "healthy" if all(
        v == "healthy" for v in services.values()
    ) else "degraded"

    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        environment=settings.app_env,
        services=services,
    )


@router.get(
    "/ready",
    status_code=status.HTTP_200_OK,
    summary="Readiness Probe",
)
async def readiness() -> dict:
    """Kubernetes readiness probe."""
    return {"status": "ready"}


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness Probe",
)
async def liveness() -> dict:
    """Kubernetes liveness probe."""
    return {"status": "alive"}

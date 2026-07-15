"""
Test Health Check Endpoints
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient):
    """Test liveness probe returns alive status."""
    response = await client.get("/api/v1/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness(client: AsyncClient):
    """Test readiness probe returns ready status."""
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

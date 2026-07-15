"""
Integration tests for Knowledge Graph (require running Neo4j).

Run with: pytest tests/integration/graph/ -v --override-ini="addopts="
Requires: Neo4j running on bolt://localhost:7687
"""

import numpy as np
import pandas as pd
import pytest

from app.graph.connection import Neo4jConnectionManager

# Skip all tests if Neo4j is not available
pytestmark = pytest.mark.skipif(
    True,  # Set to False when Neo4j is running
    reason="Neo4j not available for integration tests",
)


def _make_sample_df(n_rows: int = 100) -> pd.DataFrame:
    np.random.seed(42)
    return pd.DataFrame({
        "Order Id": [f"ORD-{i}" for i in range(n_rows)],
        "Department Name": np.random.choice(["Electronics", "Clothing"], n_rows),
        "Category Name": np.random.choice(["Phones", "Shirts"], n_rows),
        "Order City": np.random.choice(["Chicago", "New York"], n_rows),
        "Order Region": np.random.choice(["Central US", "East US"], n_rows),
        "Shipping Mode": np.random.choice(["Standard Class", "First Class"], n_rows),
        "Customer Id": [f"CUST-{i % 10}" for i in range(n_rows)],
        "Customer Segment": np.random.choice(["Consumer", "Corporate"], n_rows),
        "order date (DateOrders)": pd.date_range("2020-01-01", periods=n_rows, freq="D").astype(str),
        "Order Item Quantity": np.random.randint(1, 20, n_rows),
        "Sales": np.random.uniform(10, 1000, n_rows),
        "Order Profit Per Order": np.random.uniform(-50, 200, n_rows),
        "Days for shipping (real)": np.random.randint(1, 10, n_rows),
        "Days for shipment (scheduled)": np.random.randint(1, 7, n_rows),
        "Late_delivery_risk": np.random.randint(0, 2, n_rows),
        "order_month": np.random.randint(1, 13, n_rows),
        "order_is_weekend": np.random.randint(0, 2, n_rows),
    })


@pytest.fixture
async def connection():
    conn = Neo4jConnectionManager()
    await conn.connect()
    yield conn
    # Cleanup test data
    await conn.execute_write("MATCH (n) DETACH DELETE n")
    await conn.disconnect()


class TestNeo4jConnection:
    @pytest.mark.asyncio
    async def test_health_check(self, connection):
        assert await connection.health_check() is True

    @pytest.mark.asyncio
    async def test_execute_query(self, connection):
        records = await connection.execute_query("RETURN 1 AS value")
        assert records[0]["value"] == 1


class TestGraphBuildIntegration:
    @pytest.mark.asyncio
    async def test_full_build(self, connection):
        from app.graph.services import GraphService

        service = GraphService(connection)
        df = _make_sample_df(100)
        result = await service.build_graph(df, clear_existing=True, order_sample_size=50)

        assert result.nodes_created > 0
        assert result.relationships_created > 0
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_statistics_after_build(self, connection):
        from app.graph.services import GraphService

        service = GraphService(connection)
        df = _make_sample_df(50)
        await service.build_graph(df, clear_existing=True, order_sample_size=20)

        stats = await service.get_statistics()
        assert stats.total_nodes > 0
        assert stats.total_relationships > 0

    @pytest.mark.asyncio
    async def test_validation_after_build(self, connection):
        from app.graph.services import GraphService

        service = GraphService(connection)
        df = _make_sample_df(50)
        await service.build_graph(df, clear_existing=True, order_sample_size=20)

        result = await service.validate_graph()
        assert result.total_checks > 0


class TestGraphRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_node(self, connection):
        from app.graph.repository import GraphRepository

        repo = GraphRepository(connection)
        node = await repo.create_node("Supplier", {
            "node_id": "test_s001",
            "supplier_name": "Test Supplier",
            "risk_score": 0.5,
        })
        assert node is not None

        fetched = await repo.get_node("Supplier", "test_s001")
        assert fetched is not None
        assert fetched["supplier_name"] == "Test Supplier"

    @pytest.mark.asyncio
    async def test_update_node(self, connection):
        from app.graph.repository import GraphRepository

        repo = GraphRepository(connection)
        await repo.create_node("Supplier", {"node_id": "test_s002", "risk_score": 0.3})
        updated = await repo.update_node("Supplier", "test_s002", {"risk_score": 0.8})
        assert updated is not None
        assert updated["risk_score"] == 0.8

    @pytest.mark.asyncio
    async def test_delete_node(self, connection):
        from app.graph.repository import GraphRepository

        repo = GraphRepository(connection)
        await repo.create_node("Supplier", {"node_id": "test_s003"})
        deleted = await repo.delete_node("Supplier", "test_s003")
        assert deleted is True

        fetched = await repo.get_node("Supplier", "test_s003")
        assert fetched is None

    @pytest.mark.asyncio
    async def test_create_relationship(self, connection):
        from app.graph.repository import GraphRepository

        repo = GraphRepository(connection)
        await repo.create_node("Supplier", {"node_id": "rel_s001"})
        await repo.create_node("Product", {"node_id": "rel_p001"})

        rel = await repo.create_relationship(
            "Supplier", "rel_s001", "Product", "rel_p001", "SUPPLIES",
            {"relationship_strength": 0.9},
        )
        assert rel is not None


class TestGraphAnalytics:
    @pytest.mark.asyncio
    async def test_degree_centrality(self, connection):
        from app.graph.analytics import GraphAnalytics
        from app.graph.services import GraphService

        service = GraphService(connection)
        df = _make_sample_df(50)
        await service.build_graph(df, clear_existing=True, order_sample_size=20)

        analytics = GraphAnalytics(connection)
        results = await analytics.degree_centrality("Supplier", top_n=5)
        assert len(results) > 0
        assert "centrality" in results[0]

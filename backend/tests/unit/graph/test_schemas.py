"""
Unit tests for Graph Schemas.
"""

import pytest

from app.graph.schemas import (
    BuildResultSchema,
    EntitySchema,
    GraphBuildRequest,
    GraphStatisticsSchema,
    NodeListSchema,
    SubgraphSchema,
    ValidationResultSchema,
)


class TestGraphBuildRequest:
    def test_defaults(self):
        req = GraphBuildRequest()
        assert req.dataset_version == ""
        assert req.clear_existing is False
        assert req.order_sample_size == 5000

    def test_custom_values(self):
        req = GraphBuildRequest(
            dataset_version="v1.0",
            clear_existing=True,
            order_sample_size=1000,
        )
        assert req.dataset_version == "v1.0"
        assert req.clear_existing is True


class TestBuildResultSchema:
    def test_creation(self):
        result = BuildResultSchema(
            nodes_created=100,
            relationships_created=250,
            duration_ms=1500.0,
            graph_version="v_123",
        )
        assert result.nodes_created == 100
        assert result.relationships_created == 250


class TestGraphStatisticsSchema:
    def test_creation(self):
        stats = GraphStatisticsSchema(
            total_nodes=500,
            total_relationships=1200,
            node_counts={"Supplier": 10, "Product": 50},
            graph_density=0.005,
        )
        assert stats.total_nodes == 500
        assert stats.node_counts["Supplier"] == 10


class TestValidationResultSchema:
    def test_valid(self):
        result = ValidationResultSchema(is_valid=True, checks_passed=10, total_checks=10)
        assert result.is_valid is True

    def test_invalid(self):
        result = ValidationResultSchema(
            is_valid=False,
            checks_failed=2,
            total_checks=10,
            issues=[{"severity": "error", "category": "test", "message": "fail", "details": {}}],
        )
        assert result.is_valid is False
        assert len(result.issues) == 1


class TestEntitySchema:
    def test_creation(self):
        entity = EntitySchema(
            entity={"node_id": "s001", "label": "Supplier"},
            connections=[{"rel_type": "SUPPLIES", "connected_id": "p001"}],
        )
        assert entity.entity["node_id"] == "s001"
        assert len(entity.connections) == 1


class TestSubgraphSchema:
    def test_creation(self):
        sg = SubgraphSchema(
            center_node={"node_id": "s001"},
            neighbors=[{"node_id": "p001"}],
            edges=[{"type": "SUPPLIES"}],
        )
        assert sg.center_node["node_id"] == "s001"
        assert len(sg.neighbors) == 1

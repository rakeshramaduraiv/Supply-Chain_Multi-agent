"""
Unit tests for Graph Relationship definitions.
"""

import pytest

from app.graph.relationships import (
    BaseRelationship,
    create_contains,
    create_delivered_to,
    create_influences,
    create_placed,
    create_ships_via,
    create_stored_in,
    create_supplies,
)


class TestBaseRelationship:
    def test_creation(self):
        rel = BaseRelationship(
            rel_type="SUPPLIES",
            source_id="s001",
            source_label="Supplier",
            target_id="p001",
            target_label="Product",
            relationship_strength=0.8,
            frequency=50,
        )
        assert rel.rel_type == "SUPPLIES"
        assert rel.relationship_strength == 0.8

    def test_to_dict(self):
        rel = BaseRelationship(
            rel_type="TEST",
            source_id="a",
            source_label="A",
            target_id="b",
            target_label="B",
        )
        d = rel.to_dict()
        assert "rel_type" in d
        assert "source_id" in d
        assert "created_at" in d

    def test_properties(self):
        rel = BaseRelationship(
            rel_type="TEST",
            source_id="a",
            source_label="A",
            target_id="b",
            target_label="B",
            relationship_strength=0.9,
            frequency=10,
        )
        props = rel.properties
        assert "relationship_strength" in props
        assert "frequency" in props
        assert "source_id" not in props
        assert "rel_type" not in props


class TestFactoryFunctions:
    def test_create_supplies(self):
        rel = create_supplies("s001", "Supplier", "p001", "Product", frequency=5)
        assert rel.rel_type == "SUPPLIES"
        assert rel.source_id == "s001"
        assert rel.target_id == "p001"
        assert rel.frequency == 5

    def test_create_stored_in(self):
        rel = create_stored_in("p001", "Product", "w001", "Warehouse")
        assert rel.rel_type == "STORED_IN"

    def test_create_ships_via(self):
        rel = create_ships_via("o001", "Order", "sh001", "Shipment")
        assert rel.rel_type == "SHIPS_VIA"

    def test_create_delivered_to(self):
        rel = create_delivered_to("sh001", "Shipment", "c001", "Customer")
        assert rel.rel_type == "DELIVERED_TO"

    def test_create_placed(self):
        rel = create_placed("c001", "Customer", "o001", "Order")
        assert rel.rel_type == "PLACED"

    def test_create_contains(self):
        rel = create_contains("o001", "Order", "p001", "Product")
        assert rel.rel_type == "CONTAINS"

    def test_create_influences(self):
        rel = create_influences("ce001", "CalendarEvent", "o001", "Order")
        assert rel.rel_type == "INFLUENCES"

    def test_factory_with_kwargs(self):
        rel = create_supplies(
            "s001", "Supplier", "p001", "Product",
            relationship_strength=0.95,
            confidence=0.8,
            avg_delay=1.5,
        )
        assert rel.relationship_strength == 0.95
        assert rel.confidence == 0.8
        assert rel.avg_delay == 1.5

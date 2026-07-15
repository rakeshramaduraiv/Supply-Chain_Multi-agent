"""
Unit tests for Graph Node definitions.
"""

import pytest

from app.graph.nodes import (
    BaseNode,
    CalendarEventNode,
    CustomerNode,
    OrderNode,
    ProductNode,
    ShipmentNode,
    SupplierNode,
    WarehouseNode,
)


class TestSupplierNode:
    def test_creation(self):
        node = SupplierNode(
            node_id="s001",
            supplier_id="s001",
            supplier_name="Acme Corp",
            risk_score=0.3,
            total_orders=100,
        )
        assert node.label == "Supplier"
        assert node.supplier_name == "Acme Corp"
        assert node.risk_score == 0.3

    def test_to_dict(self):
        node = SupplierNode(node_id="s001", supplier_id="s001", supplier_name="Test")
        d = node.to_dict()
        assert "node_id" in d
        assert "supplier_name" in d
        assert "label" in d
        assert d["label"] == "Supplier"


class TestProductNode:
    def test_creation(self):
        node = ProductNode(
            node_id="p001",
            product_id="p001",
            category="Electronics",
            rolling_7d_demand=15.5,
            demand_volatility=0.3,
        )
        assert node.label == "Product"
        assert node.category == "Electronics"
        assert node.rolling_7d_demand == 15.5


class TestWarehouseNode:
    def test_creation(self):
        node = WarehouseNode(
            node_id="w001",
            warehouse_id="w001",
            city="Chicago",
            region="Central US",
            warehouse_risk=0.4,
        )
        assert node.city == "Chicago"
        assert node.region == "Central US"


class TestShipmentNode:
    def test_creation(self):
        node = ShipmentNode(
            node_id="sh001",
            shipment_id="sh001",
            shipping_mode="Standard Class",
            scheduled_days=5.0,
            actual_days=7.0,
            shipping_delay=2.0,
        )
        assert node.shipping_mode == "Standard Class"
        assert node.shipping_delay == 2.0


class TestCustomerNode:
    def test_creation(self):
        node = CustomerNode(
            node_id="c001",
            customer_id="c001",
            segment="Consumer",
            total_orders=25,
            avg_order_value=150.0,
        )
        assert node.segment == "Consumer"
        assert node.total_orders == 25


class TestOrderNode:
    def test_creation(self):
        node = OrderNode(
            node_id="o001",
            order_id="o001",
            order_date="2023-01-15",
            order_value=250.0,
            order_quantity=3,
            risk_score=0.7,
        )
        assert node.order_value == 250.0
        assert node.risk_score == 0.7


class TestCalendarEventNode:
    def test_creation(self):
        node = CalendarEventNode(
            node_id="ce001",
            event_id="ce001",
            event_name="December",
            event_type="monthly_period",
            is_holiday=True,
        )
        assert node.event_name == "December"
        assert node.is_holiday is True

"""
Unit tests for Entity Extractor module.
"""

import numpy as np
import pandas as pd
import pytest

from app.graph.extractor import EntityExtractor


def _make_sample_df(n_rows: int = 200) -> pd.DataFrame:
    """Create a sample engineered DataFrame."""
    np.random.seed(42)
    departments = ["Electronics", "Clothing", "Food", "Furniture"]
    categories = ["Phones", "Shirts", "Snacks", "Tables"]
    cities = ["Chicago", "New York", "Los Angeles", "Houston"]
    regions = ["Central US", "East US", "West US", "South US"]
    modes = ["Standard Class", "First Class", "Second Class", "Same Day"]
    segments = ["Consumer", "Corporate", "Home Office"]

    return pd.DataFrame({
        "Order Id": [f"ORD-{i}" for i in range(n_rows)],
        "Department Name": np.random.choice(departments, n_rows),
        "Category Name": np.random.choice(categories, n_rows),
        "Order City": np.random.choice(cities, n_rows),
        "Order Region": np.random.choice(regions, n_rows),
        "Shipping Mode": np.random.choice(modes, n_rows),
        "Customer Id": [f"CUST-{i % 50}" for i in range(n_rows)],
        "Customer Segment": np.random.choice(segments, n_rows),
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
def extractor():
    return EntityExtractor()


@pytest.fixture
def sample_df():
    return _make_sample_df()


class TestExtractSuppliers:
    def test_extracts_suppliers(self, extractor, sample_df):
        suppliers = extractor.extract_suppliers(sample_df)
        assert len(suppliers) == 4  # 4 departments
        for s in suppliers:
            assert s.label == "Supplier"
            assert s.supplier_name != ""
            assert 0 <= s.risk_score <= 1.0
            assert s.total_orders > 0

    def test_empty_df(self, extractor):
        df = pd.DataFrame()
        assert extractor.extract_suppliers(df) == []


class TestExtractProducts:
    def test_extracts_products(self, extractor, sample_df):
        products = extractor.extract_products(sample_df)
        assert len(products) == 4  # 4 categories
        for p in products:
            assert p.label == "Product"
            assert p.category != ""
            assert p.rolling_7d_demand >= 0

    def test_demand_metrics(self, extractor, sample_df):
        products = extractor.extract_products(sample_df)
        for p in products:
            assert p.demand_volatility >= 0
            assert 0 <= p.inventory_stress <= 1.0
            assert 0 <= p.forecast_risk <= 1.0


class TestExtractWarehouses:
    def test_extracts_warehouses(self, extractor, sample_df):
        warehouses = extractor.extract_warehouses(sample_df)
        assert len(warehouses) == 4  # 4 cities
        for w in warehouses:
            assert w.label == "Warehouse"
            assert w.city != ""
            assert 0 <= w.warehouse_risk <= 1.0

    def test_coverage_ratio(self, extractor, sample_df):
        warehouses = extractor.extract_warehouses(sample_df)
        for w in warehouses:
            assert 0 <= w.stock_coverage_ratio <= 1.0


class TestExtractShipments:
    def test_extracts_shipments(self, extractor, sample_df):
        shipments = extractor.extract_shipments(sample_df)
        assert len(shipments) == 4  # 4 shipping modes
        for s in shipments:
            assert s.label == "Shipment"
            assert s.shipping_mode != ""
            assert s.scheduled_days > 0

    def test_efficiency_score(self, extractor, sample_df):
        shipments = extractor.extract_shipments(sample_df)
        for s in shipments:
            assert 0 <= s.shipping_efficiency_score <= 1.0
            assert 0 <= s.late_delivery_rate <= 1.0


class TestExtractCustomers:
    def test_extracts_customers(self, extractor, sample_df):
        customers = extractor.extract_customers(sample_df)
        assert len(customers) == 50  # 50 unique customers
        for c in customers:
            assert c.label == "Customer"
            assert c.customer_id != ""
            assert c.total_orders > 0

    def test_customer_metrics(self, extractor, sample_df):
        customers = extractor.extract_customers(sample_df)
        for c in customers:
            assert c.avg_order_value > 0


class TestExtractOrders:
    def test_extracts_orders(self, extractor, sample_df):
        orders = extractor.extract_orders(sample_df, sample_size=100)
        assert len(orders) <= 200  # Unique orders
        for o in orders:
            assert o.label == "Order"
            assert o.order_id != ""

    def test_sample_size_limit(self, extractor, sample_df):
        orders = extractor.extract_orders(sample_df, sample_size=10)
        assert len(orders) <= 10


class TestExtractCalendarEvents:
    def test_extracts_events(self, extractor, sample_df):
        events = extractor.extract_calendar_events(sample_df)
        assert len(events) > 0
        for e in events:
            assert e.label == "CalendarEvent"
            assert e.event_name != ""

    def test_includes_weekend(self, extractor, sample_df):
        events = extractor.extract_calendar_events(sample_df)
        names = [e.event_name for e in events]
        assert "Weekend" in names


class TestExtractRelationships:
    def test_extracts_relationships(self, extractor, sample_df):
        suppliers = extractor.extract_suppliers(sample_df)
        products = extractor.extract_products(sample_df)
        warehouses = extractor.extract_warehouses(sample_df)
        shipments = extractor.extract_shipments(sample_df)
        customers = extractor.extract_customers(sample_df)
        orders = extractor.extract_orders(sample_df, sample_size=50)
        events = extractor.extract_calendar_events(sample_df)

        rels = extractor.extract_relationships(
            sample_df, suppliers, products, warehouses,
            shipments, customers, orders, events,
        )
        assert len(rels) > 0

        # Check relationship types present
        rel_types = set(r.rel_type for r in rels)
        assert "SUPPLIES" in rel_types
        assert "STORED_IN" in rel_types

    def test_relationship_properties(self, extractor, sample_df):
        suppliers = extractor.extract_suppliers(sample_df)
        products = extractor.extract_products(sample_df)
        rels = extractor.extract_relationships(
            sample_df, suppliers, products, [], [], [], [], [],
        )
        for r in rels:
            assert r.relationship_strength > 0
            assert r.confidence > 0
            assert r.created_at != ""

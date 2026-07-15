"""
AMASCI Neo4j Schema Manager
===============================
Production-ready schema initialization: constraints, indexes, full-text search.
Ensures idempotent execution (IF NOT EXISTS).
"""

import logging
from typing import Any

from app.graph.connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# UNIQUENESS CONSTRAINTS
# ─────────────────────────────────────────────────────────────────────────────

UNIQUENESS_CONSTRAINTS = [
    ("constraint_supplier_node_id", "Supplier", "node_id"),
    ("constraint_product_node_id", "Product", "node_id"),
    ("constraint_warehouse_node_id", "Warehouse", "node_id"),
    ("constraint_shipment_node_id", "Shipment", "node_id"),
    ("constraint_customer_node_id", "Customer", "node_id"),
    ("constraint_order_node_id", "Order", "node_id"),
    ("constraint_calendar_event_node_id", "CalendarEvent", "node_id"),
]

# ─────────────────────────────────────────────────────────────────────────────
# PROPERTY EXISTENCE CONSTRAINTS (Enterprise Edition only — wrapped in try)
# ─────────────────────────────────────────────────────────────────────────────

EXISTENCE_CONSTRAINTS = [
    ("constraint_supplier_name_exists", "Supplier", "supplier_name"),
    ("constraint_product_category_exists", "Product", "category"),
    ("constraint_warehouse_city_exists", "Warehouse", "city"),
    ("constraint_shipment_mode_exists", "Shipment", "shipping_mode"),
    ("constraint_customer_id_exists", "Customer", "customer_id"),
    ("constraint_order_id_exists", "Order", "order_id"),
    ("constraint_event_name_exists", "CalendarEvent", "event_name"),
]

# ─────────────────────────────────────────────────────────────────────────────
# INDEXES (B-Tree for filtering, range queries)
# ─────────────────────────────────────────────────────────────────────────────

BTREE_INDEXES = [
    # Supplier indexes
    ("idx_supplier_name", "Supplier", ["supplier_name"]),
    ("idx_supplier_risk", "Supplier", ["risk_score"]),
    ("idx_supplier_reliability", "Supplier", ["supplier_reliability_score"]),
    # Product indexes
    ("idx_product_category", "Product", ["category"]),
    ("idx_product_forecast_risk", "Product", ["forecast_risk"]),
    ("idx_product_demand_volatility", "Product", ["demand_volatility"]),
    # Warehouse indexes
    ("idx_warehouse_city", "Warehouse", ["city"]),
    ("idx_warehouse_region", "Warehouse", ["region"]),
    ("idx_warehouse_risk", "Warehouse", ["warehouse_risk"]),
    # Shipment indexes
    ("idx_shipment_mode", "Shipment", ["shipping_mode"]),
    ("idx_shipment_late_rate", "Shipment", ["late_delivery_rate"]),
    # Customer indexes
    ("idx_customer_segment", "Customer", ["segment"]),
    ("idx_customer_region", "Customer", ["region"]),
    # Order indexes
    ("idx_order_id", "Order", ["order_id"]),
    ("idx_order_risk", "Order", ["risk_score"]),
    ("idx_order_date", "Order", ["order_date"]),
    # CalendarEvent indexes
    ("idx_event_type", "CalendarEvent", ["event_type"]),
    # Temporal indexes (all nodes)
    ("idx_supplier_updated", "Supplier", ["updated_at"]),
    ("idx_product_updated", "Product", ["updated_at"]),
    ("idx_warehouse_updated", "Warehouse", ["updated_at"]),
    ("idx_order_updated", "Order", ["updated_at"]),
]

# ─────────────────────────────────────────────────────────────────────────────
# FULL-TEXT INDEXES (for search)
# ─────────────────────────────────────────────────────────────────────────────

FULLTEXT_INDEXES = [
    ("ft_supplier_search", ["Supplier"], ["supplier_name"]),
    ("ft_product_search", ["Product"], ["category"]),
    ("ft_warehouse_search", ["Warehouse"], ["city", "region"]),
    ("ft_customer_search", ["Customer"], ["customer_id", "segment"]),
    ("ft_order_search", ["Order"], ["order_id"]),
]


class Neo4jSchemaManager:
    """
    Manages Neo4j schema: constraints, indexes, full-text search.
    All operations are idempotent (IF NOT EXISTS).
    """

    def __init__(self, connection: Neo4jConnectionManager):
        self._conn = connection

    async def initialize_schema(self) -> dict[str, Any]:
        """Run full schema initialization. Returns summary."""
        results = {
            "constraints_created": 0,
            "indexes_created": 0,
            "fulltext_indexes_created": 0,
            "errors": [],
        }

        # Uniqueness constraints
        for name, label, prop in UNIQUENESS_CONSTRAINTS:
            try:
                await self._conn.execute_write(
                    f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
                )
                results["constraints_created"] += 1
            except Exception as e:
                results["errors"].append(f"Constraint {name}: {e}")

        # Existence constraints (Enterprise only)
        for name, label, prop in EXISTENCE_CONSTRAINTS:
            try:
                await self._conn.execute_write(
                    f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS NOT NULL"
                )
                results["constraints_created"] += 1
            except Exception as e:
                # Expected to fail on Community Edition
                logger.debug(f"Existence constraint skipped (Community Edition): {name}")

        # B-Tree indexes
        for name, label, props in BTREE_INDEXES:
            try:
                prop_list = ", ".join(f"n.{p}" for p in props)
                await self._conn.execute_write(
                    f"CREATE INDEX {name} IF NOT EXISTS FOR (n:{label}) ON ({prop_list})"
                )
                results["indexes_created"] += 1
            except Exception as e:
                results["errors"].append(f"Index {name}: {e}")

        # Full-text indexes
        for name, labels, props in FULLTEXT_INDEXES:
            try:
                label_str = "|".join(labels)
                prop_str = ", ".join(f"n.{p}" for p in props)
                await self._conn.execute_write(
                    f"CREATE FULLTEXT INDEX {name} IF NOT EXISTS FOR (n:{label_str}) ON EACH [{prop_str}]"
                )
                results["fulltext_indexes_created"] += 1
            except Exception as e:
                results["errors"].append(f"Fulltext {name}: {e}")

        total = results["constraints_created"] + results["indexes_created"] + results["fulltext_indexes_created"]
        logger.info(f"Schema initialized: {total} objects created, {len(results['errors'])} errors")
        return results

    async def drop_all_constraints(self) -> int:
        """Drop all constraints (for testing/reset)."""
        records = await self._conn.execute_query("SHOW CONSTRAINTS YIELD name RETURN name")
        count = 0
        for r in records:
            try:
                await self._conn.execute_write(f"DROP CONSTRAINT {r['name']} IF EXISTS")
                count += 1
            except Exception:
                pass
        return count

    async def drop_all_indexes(self) -> int:
        """Drop all indexes (for testing/reset)."""
        records = await self._conn.execute_query("SHOW INDEXES YIELD name WHERE name STARTS WITH 'idx_' OR name STARTS WITH 'ft_' RETURN name")
        count = 0
        for r in records:
            try:
                await self._conn.execute_write(f"DROP INDEX {r['name']} IF EXISTS")
                count += 1
            except Exception:
                pass
        return count

    async def get_schema_info(self) -> dict[str, Any]:
        """Get current schema state."""
        constraints = await self._conn.execute_query("SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN name, type, labelsOrTypes, properties")
        indexes = await self._conn.execute_query("SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state RETURN name, type, labelsOrTypes, properties, state")
        return {
            "constraints": constraints,
            "indexes": indexes,
            "constraint_count": len(constraints),
            "index_count": len(indexes),
        }

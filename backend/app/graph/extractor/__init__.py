"""
AMASCI Entity Extractor
=========================
Extracts graph entities from engineered supply chain datasets.
Transforms aggregated business features into node objects.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.graph.nodes import (
    CalendarEventNode,
    CustomerNode,
    OrderNode,
    ProductNode,
    ShipmentNode,
    SupplierNode,
    WarehouseNode,
)
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
from app.graph.utils import generate_node_id, safe_float, safe_int, safe_str, utc_now_iso, normalize_entity_name, slugify_entity_name

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    Extracts supply chain entities and relationships from an engineered DataFrame.

    Aggregates row-level data into entity-level nodes with computed business features.
    """

    def extract_suppliers(self, df: pd.DataFrame) -> list[SupplierNode]:
        """Extract unique supplier nodes with aggregated metrics."""
        if "Department Name" not in df.columns:
            return []

        suppliers = []
        # Normalize department names before grouping (#4)
        df = df.copy()
        df["_dept_norm"] = df["Department Name"].apply(normalize_entity_name)
        grouped = df.groupby("_dept_norm")

        for name, group in grouped:
            if not name:
                continue
            supplier_id = generate_node_id("Supplier", name)
            total_orders = len(group)

            # Prefer engineered features (Fix 1) over raw CSV derivation
            if "supplier_reliability_score" in group.columns:
                reliability = safe_float(group["supplier_reliability_score"].mean(), 0.5)
            elif "Late_delivery_risk" in group.columns:
                late_count = group["Late_delivery_risk"].sum()
                delay_rate_raw = float(late_count / total_orders) if total_orders > 0 else 0.0
                reliability = max(0.0, 1.0 - delay_rate_raw)
            else:
                reliability = 0.5

            if "supplier_delay_rate" in group.columns:
                delay_rate = safe_float(group["supplier_delay_rate"].mean(), 0.3)
            elif "Late_delivery_risk" in group.columns:
                delay_rate = float(group["Late_delivery_risk"].sum() / total_orders) if total_orders > 0 else 0.3
            else:
                delay_rate = 0.3

            avg_real  = group["Days for shipping (real)"].mean()       if "Days for shipping (real)"       in group.columns else 0
            avg_sched = group["Days for shipment (scheduled)"].mean()  if "Days for shipment (scheduled)"  in group.columns else 0
            avg_delay_days = safe_float(avg_real - avg_sched, 0.0) if avg_real and avg_sched else 0.0

            if "shipping_delay_ratio" in group.columns:
                shipping_efficiency = safe_float(1.0 - group["shipping_delay_ratio"].mean(), 1.0)
            else:
                shipping_efficiency = max(0.0, 1.0 - delay_rate)

            risk_score = min(1.0, delay_rate * 0.5 + min(max(avg_delay_days, 0) / 7.0, 1.0) * 0.5)

            suppliers.append(SupplierNode(
                node_id=supplier_id,
                supplier_id=supplier_id,
                supplier_name=safe_str(name),
                # Property names match get_agent_context() Cypher RETURN aliases
                supplier_reliability_score=round(reliability, 4),
                reliability_score=round(reliability, 4),
                supplier_delay_rate=round(delay_rate, 4),
                shipping_efficiency_score=round(shipping_efficiency, 4),
                avg_delay=round(avg_delay_days, 2),
                avg_delay_days=round(avg_delay_days, 2),
                total_orders=total_orders,
                risk_score=round(risk_score, 4),
            ))

        logger.info(f"Extracted {len(suppliers)} supplier nodes")
        return suppliers

    def extract_products(self, df: pd.DataFrame) -> list[ProductNode]:
        """Extract unique product nodes with demand features."""
        cat_col = "Category Name"
        if cat_col not in df.columns:
            return []

        products = []
        # Normalize category names before grouping (#4)
        df = df.copy()
        df["_cat_norm"] = df[cat_col].apply(normalize_entity_name)
        grouped = df.groupby("_cat_norm")

        for category, group in grouped:
            if not category:
                continue
            product_id = generate_node_id("Product", category)
            qty_col = "Order Item Quantity"

            quantities = group[qty_col] if qty_col in group.columns else pd.Series([0])
            rolling_7d  = float(quantities.tail(7).mean())  if len(quantities) >= 7  else float(quantities.mean())
            rolling_30d = float(quantities.tail(30).mean()) if len(quantities) >= 30 else float(quantities.mean())

            # Prefer engineered features (Fix 1) over raw derivation
            volatility = (
                safe_float(group["demand_volatility"].mean())
                if "demand_volatility" in group.columns
                else safe_float(quantities.std() / quantities.mean() if quantities.mean() > 0 else 0.0)
            )
            # demand_trend_slope is the exact property name read by get_agent_context()
            demand_trend_slope = (
                safe_float(group["demand_trend_slope"].mean())
                if "demand_trend_slope" in group.columns
                else safe_float(quantities.tail(7).mean() - quantities.head(7).mean() if len(quantities) >= 14 else 0.0)
            )
            demand_momentum = (
                safe_float(group["demand_momentum"].mean())
                if "demand_momentum" in group.columns
                else 0.0
            )
            avg_spike_rate = (
                safe_float(group["demand_spike_flag"].mean())
                if "demand_spike_flag" in group.columns
                else 0.0
            )

            late_rate = group["Late_delivery_risk"].mean() if "Late_delivery_risk" in group.columns else 0.0
            inventory_stress = min(1.0, volatility * 0.5 + safe_float(late_rate) * 0.5)
            forecast_risk    = min(1.0, volatility * 0.4 + safe_float(late_rate) * 0.3 + abs(demand_trend_slope) / (rolling_30d + 1) * 0.3)

            products.append(ProductNode(
                node_id=product_id,
                product_id=product_id,
                category=safe_str(category),
                rolling_7d_demand=round(safe_float(rolling_7d), 2),
                rolling_30d_demand=round(safe_float(rolling_30d), 2),
                # Property names match get_agent_context() Cypher RETURN aliases
                demand_volatility=round(volatility, 4),
                demand_trend=round(demand_trend_slope, 4),
                demand_trend_slope=round(demand_trend_slope, 4),
                demand_momentum=round(demand_momentum, 4),
                avg_spike_rate=round(avg_spike_rate, 4),
                inventory_stress=round(inventory_stress, 4),
                forecast_risk=round(forecast_risk, 4),
            ))

        logger.info(f"Extracted {len(products)} product nodes")
        return products

    def extract_warehouses(self, df: pd.DataFrame) -> list[WarehouseNode]:
        """Extract warehouse nodes from city/region data."""
        city_col   = "Order City"
        region_col = "Order Region"
        if city_col not in df.columns:
            return []

        warehouses = []
        # Normalize city names before grouping (#4)
        df = df.copy()
        df["_city_norm"] = df[city_col].apply(normalize_entity_name)
        grouped = df.groupby("_city_norm")

        for city, group in grouped:
            if not city:
                continue
            warehouse_id = generate_node_id("Warehouse", city)
            region = safe_str(group[region_col].iloc[0]) if region_col in group.columns else ""
            total = len(group)
            late_count = group["Late_delivery_risk"].sum() if "Late_delivery_risk" in group.columns else 0
            late_rate  = float(late_count / total) if total > 0 else 0.0

            # Prefer engineered features (Fix 1) — property names match get_agent_context() aliases
            avg_inventory_stress = (
                safe_float(group["inventory_stress_index"].mean())
                if "inventory_stress_index" in group.columns
                else min(1.0, late_rate * 0.6 + min(safe_float(group["Order Item Quantity"].mean() if "Order Item Quantity" in group.columns else 0) / 20.0, 1.0) * 0.4)
            )
            avg_days_to_reorder = (
                safe_float(group["days_until_reorder"].mean())
                if "days_until_reorder" in group.columns
                else max(0.0, (1.0 - avg_inventory_stress) * 30.0)
            )
            avg_coverage_ratio = (
                safe_float(group["stock_coverage_ratio"].mean())
                if "stock_coverage_ratio" in group.columns
                else max(0.0, 1.0 - late_rate)
            )
            warehouse_risk = min(1.0, avg_inventory_stress * 0.7 + late_rate * 0.3)

            warehouses.append(WarehouseNode(
                node_id=warehouse_id,
                warehouse_id=warehouse_id,
                city=safe_str(city),
                region=region,
                location_region=region,
                # Property names match get_agent_context() Cypher RETURN aliases
                stock_coverage_ratio=round(avg_coverage_ratio, 4),
                inventory_stress_index=round(avg_inventory_stress, 4),
                avg_inventory_stress=round(avg_inventory_stress, 4),
                days_until_reorder=round(avg_days_to_reorder, 1),
                avg_days_to_reorder=round(avg_days_to_reorder, 1),
                avg_coverage_ratio=round(avg_coverage_ratio, 4),
                warehouse_risk=round(warehouse_risk, 4),
            ))

        logger.info(f"Extracted {len(warehouses)} warehouse nodes")
        return warehouses

    def extract_shipments(self, df: pd.DataFrame) -> list[ShipmentNode]:
        """Extract shipment nodes aggregated by shipping mode."""
        mode_col = "Shipping Mode"
        if mode_col not in df.columns:
            return []

        shipments = []
        grouped = df.groupby(mode_col)

        for mode, group in grouped:
            shipment_id = generate_node_id("Shipment", mode)
            sched = group["Days for shipment (scheduled)"].mean() if "Days for shipment (scheduled)" in group.columns else 0
            actual = group["Days for shipping (real)"].mean() if "Days for shipping (real)" in group.columns else 0
            delay = float(actual - sched)
            late_count = group["Late_delivery_risk"].sum() if "Late_delivery_risk" in group.columns else 0
            total = len(group)
            late_rate = float(late_count / total) if total > 0 else 0.0
            efficiency = max(0.0, 1.0 - late_rate)

            shipments.append(ShipmentNode(
                node_id=shipment_id,
                shipment_id=shipment_id,
                shipping_mode=safe_str(mode),
                scheduled_days=round(safe_float(sched), 2),
                actual_days=round(safe_float(actual), 2),
                shipping_delay=round(safe_float(delay), 2),
                shipping_efficiency_score=round(efficiency, 4),
                late_delivery_rate=round(late_rate, 4),
            ))

        logger.info(f"Extracted {len(shipments)} shipment nodes")
        return shipments

    def extract_customers(self, df: pd.DataFrame) -> list[CustomerNode]:
        """Extract customer nodes with aggregated metrics."""
        cust_col = "Customer Id"
        if cust_col not in df.columns:
            return []

        customers = []
        grouped = df.groupby(cust_col)

        for cust_id, group in grouped:
            node_id = generate_node_id("Customer", cust_id)
            segment = safe_str(group["Customer Segment"].iloc[0]) if "Customer Segment" in group.columns else ""
            region = safe_str(group["Order Region"].iloc[0]) if "Order Region" in group.columns else ""
            total_orders = len(group)
            avg_value = float(group["Sales"].mean()) if "Sales" in group.columns else 0.0
            total_profit = float(group["Order Profit Per Order"].sum()) if "Order Profit Per Order" in group.columns else 0.0
            total_sales = float(group["Sales"].sum()) if "Sales" in group.columns else 0.0
            margin = float(total_profit / total_sales) if total_sales > 0 else 0.0

            customers.append(CustomerNode(
                node_id=node_id,
                customer_id=safe_str(cust_id),
                segment=segment,
                region=region,
                total_orders=total_orders,
                avg_order_value=round(safe_float(avg_value), 2),
                profit_margin=round(safe_float(margin), 4),
            ))

        logger.info(f"Extracted {len(customers)} customer nodes")
        return customers

    def extract_orders(
        self,
        df: pd.DataFrame,
        sample_size: int = 5000,
        strategy: str = "stratified",
    ) -> list[OrderNode]:
        """
        Extract order nodes using a sampling strategy (#10).

        strategy:
          'stratified' — sample equally from each calendar month (default)
          'all'        — load all orders (may be slow on 180k rows)
          'recent'     — load orders from the most recent 6 months
        """
        order_col = "Order Id"
        if order_col not in df.columns:
            return []

        date_col = "order date (DateOrders)"
        df = df.copy()
        if date_col in df.columns:
            df["_order_date"] = pd.to_datetime(df[date_col], errors="coerce")
        else:
            df["_order_date"] = pd.NaT

        if strategy == "all":
            sampled = df.drop_duplicates(subset=[order_col])
        elif strategy == "recent":
            max_date = df["_order_date"].max()
            cutoff   = max_date - pd.Timedelta(days=180)
            sampled  = df[df["_order_date"] >= cutoff].drop_duplicates(subset=[order_col])
        else:  # stratified (default)
            df["_month"] = df["_order_date"].dt.to_period("M").astype(str)
            per_month = max(1, sample_size // max(df["_month"].nunique(), 1))
            sampled = (
                df.groupby("_month", group_keys=False)
                .apply(lambda g: g.sample(n=min(per_month, len(g)), random_state=42))
                .drop_duplicates(subset=[order_col])
            )

        orders = []
        for _, row in sampled.iterrows():
            oid = safe_str(row.get(order_col))
            if not oid:
                continue
            node_id    = generate_node_id("Order", oid)
            order_date = safe_str(row.get(date_col, ""))
            value      = safe_float(row.get("Sales", 0))
            qty        = safe_int(row.get("Order Item Quantity", 0))
            profit     = safe_float(row.get("Order Profit Per Order", 0))
            risk       = safe_float(row.get("Late_delivery_risk", 0))

            orders.append(OrderNode(
                node_id=node_id,
                order_id=oid,
                order_date=order_date,
                order_value=round(value, 2),
                order_quantity=qty,
                profit=round(profit, 2),
                risk_score=round(risk, 4),
            ))

        logger.info(f"Extracted {len(orders)} order nodes (strategy={strategy})")
        return orders

    def extract_calendar_events(self, df: pd.DataFrame) -> list[CalendarEventNode]:
        """Extract calendar event nodes from temporal features."""
        if "order_month" not in df.columns:
            return []

        events = []
        months = df["order_month"].dropna().unique()

        month_names = {
            1: "January", 2: "February", 3: "March", 4: "April",
            5: "May", 6: "June", 7: "July", 8: "August",
            9: "September", 10: "October", 11: "November", 12: "December",
        }

        for month in sorted(months):
            m = safe_int(month)
            if m < 1 or m > 12:
                continue
            event_id = generate_node_id("CalendarEvent", f"month_{m}")
            events.append(CalendarEventNode(
                node_id=event_id,
                event_id=event_id,
                event_name=month_names.get(m, f"Month_{m}"),
                event_type="monthly_period",
                is_holiday=(m == 12),
            ))

        # Weekend events
        if "order_is_weekend" in df.columns:
            weekend_id = generate_node_id("CalendarEvent", "weekend")
            events.append(CalendarEventNode(
                node_id=weekend_id,
                event_id=weekend_id,
                event_name="Weekend",
                event_type="day_type",
                is_holiday=False,
            ))

        logger.info(f"Extracted {len(events)} calendar event nodes")
        return events

    def extract_relationships(
        self,
        df: pd.DataFrame,
        suppliers: list[SupplierNode],
        products: list[ProductNode],
        warehouses: list[WarehouseNode],
        shipments: list[ShipmentNode],
        customers: list[CustomerNode],
        orders: list[OrderNode],
        calendar_events: list[CalendarEventNode],
    ) -> list[BaseRelationship]:
        """Extract all relationships between extracted entities."""
        relationships: list[BaseRelationship] = []
        now = utc_now_iso()

        supplier_map = {s.supplier_name: s for s in suppliers}
        product_map = {p.category: p for p in products}
        warehouse_map = {w.city: w for w in warehouses}
        shipment_map = {s.shipping_mode: s for s in shipments}
        customer_map = {c.customer_id: c for c in customers}
        order_map = {o.order_id: o for o in orders}

        # SUPPLIES: Supplier → Product
        if "Department Name" in df.columns and "Category Name" in df.columns:
            supply_pairs = df.groupby(["Department Name", "Category Name"]).agg(
                freq=("Order Id", "count"),
                avg_delay_val=("Days for shipping (real)", "mean"),
            ).reset_index()

            for _, row in supply_pairs.iterrows():
                supplier = supplier_map.get(safe_str(row["Department Name"]))
                product = product_map.get(safe_str(row["Category Name"]))
                if supplier and product:
                    freq = safe_int(row["freq"])
                    strength = min(1.0, freq / supply_pairs["freq"].max()) if supply_pairs["freq"].max() > 0 else 0.5
                    relationships.append(create_supplies(
                        source_id=supplier.node_id,
                        source_label="Supplier",
                        target_id=product.node_id,
                        target_label="Product",
                        relationship_strength=round(strength, 4),
                        frequency=freq,
                        avg_delay=round(safe_float(row["avg_delay_val"]), 2),
                        confidence=0.95,
                        created_at=now,
                        updated_at=now,
                    ))

        # STORED_IN: Product → Warehouse
        if "Category Name" in df.columns and "Order City" in df.columns:
            storage_pairs = df.groupby(["Category Name", "Order City"]).size().reset_index(name="freq")
            top_storage = storage_pairs.sort_values("freq", ascending=False).groupby("Category Name").head(3)

            for _, row in top_storage.iterrows():
                product = product_map.get(safe_str(row["Category Name"]))
                warehouse = warehouse_map.get(safe_str(row["Order City"]))
                if product and warehouse:
                    freq = safe_int(row["freq"])
                    strength = min(1.0, freq / top_storage["freq"].max()) if top_storage["freq"].max() > 0 else 0.5
                    relationships.append(create_stored_in(
                        source_id=product.node_id,
                        source_label="Product",
                        target_id=warehouse.node_id,
                        target_label="Warehouse",
                        relationship_strength=round(strength, 4),
                        frequency=freq,
                        confidence=0.85,
                        created_at=now,
                        updated_at=now,
                    ))

        # SHIPS_VIA: Order → Shipment
        if "Order Id" in df.columns and "Shipping Mode" in df.columns:
            order_ship = df[["Order Id", "Shipping Mode"]].drop_duplicates()
            for _, row in order_ship.iterrows():
                oid = safe_str(row["Order Id"])
                mode = safe_str(row["Shipping Mode"])
                order = order_map.get(oid)
                shipment = shipment_map.get(mode)
                if order and shipment:
                    relationships.append(create_ships_via(
                        source_id=order.node_id,
                        source_label="Order",
                        target_id=shipment.node_id,
                        target_label="Shipment",
                        relationship_strength=1.0,
                        frequency=1,
                        confidence=1.0,
                        created_at=now,
                        updated_at=now,
                    ))

        # DELIVERED_TO: Shipment → Customer
        if "Shipping Mode" in df.columns and "Customer Id" in df.columns:
            delivery_pairs = df.groupby(["Shipping Mode", "Customer Id"]).agg(
                freq=("Order Id", "count"),
                avg_d=("Days for shipping (real)", "mean"),
            ).reset_index()
            top_deliveries = delivery_pairs.sort_values("freq", ascending=False).groupby("Shipping Mode").head(50)

            for _, row in top_deliveries.iterrows():
                shipment = shipment_map.get(safe_str(row["Shipping Mode"]))
                customer = customer_map.get(safe_str(row["Customer Id"]))
                if shipment and customer:
                    relationships.append(create_delivered_to(
                        source_id=shipment.node_id,
                        source_label="Shipment",
                        target_id=customer.node_id,
                        target_label="Customer",
                        relationship_strength=round(min(1.0, safe_int(row["freq"]) / 10.0), 4),
                        frequency=safe_int(row["freq"]),
                        avg_delay=round(safe_float(row["avg_d"]), 2),
                        confidence=0.9,
                        created_at=now,
                        updated_at=now,
                    ))

        # PLACED: Customer → Order
        if "Customer Id" in df.columns and "Order Id" in df.columns:
            for order in orders:
                matching = df[df["Order Id"].astype(str) == order.order_id]
                if len(matching) > 0:
                    cust_id = safe_str(matching.iloc[0].get("Customer Id"))
                    customer = customer_map.get(cust_id)
                    if customer:
                        relationships.append(create_placed(
                            source_id=customer.node_id,
                            source_label="Customer",
                            target_id=order.node_id,
                            target_label="Order",
                            relationship_strength=1.0,
                            frequency=1,
                            confidence=1.0,
                            created_at=now,
                            updated_at=now,
                        ))

        # CONTAINS: Order → Product
        if "Order Id" in df.columns and "Category Name" in df.columns:
            for order in orders:
                matching = df[df["Order Id"].astype(str) == order.order_id]
                if len(matching) > 0:
                    cat = safe_str(matching.iloc[0].get("Category Name"))
                    product = product_map.get(cat)
                    if product:
                        relationships.append(create_contains(
                            source_id=order.node_id,
                            source_label="Order",
                            target_id=product.node_id,
                            target_label="Product",
                            relationship_strength=1.0,
                            frequency=1,
                            confidence=1.0,
                            created_at=now,
                            updated_at=now,
                        ))

        # INFLUENCES: CalendarEvent → Order (monthly)
        if "order_month" in df.columns and calendar_events:
            month_event_map = {e.event_name: e for e in calendar_events if e.event_type == "monthly_period"}
            month_names = {
                1: "January", 2: "February", 3: "March", 4: "April",
                5: "May", 6: "June", 7: "July", 8: "August",
                9: "September", 10: "October", 11: "November", 12: "December",
            }
            for order in orders:
                matching = df[df["Order Id"].astype(str) == order.order_id]
                if len(matching) > 0:
                    month_val = safe_int(matching.iloc[0].get("order_month"))
                    month_name = month_names.get(month_val)
                    event = month_event_map.get(month_name) if month_name else None
                    if event:
                        relationships.append(create_influences(
                            source_id=event.node_id,
                            source_label="CalendarEvent",
                            target_id=order.node_id,
                            target_label="Order",
                            relationship_strength=0.7,
                            frequency=1,
                            confidence=0.8,
                            created_at=now,
                            updated_at=now,
                        ))

        logger.info(f"Extracted {len(relationships)} relationships")
        return relationships

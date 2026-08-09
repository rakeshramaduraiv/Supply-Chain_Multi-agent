"""
AMASCI Graph Node Definitions
================================
Node type schemas and property definitions for all supply chain entities.

Coarse nodes (Supplier, Shipment, Warehouse) serve TPKE and RCA.
Fine-grained enrichment nodes carry per-anchor statistics for the three
GRAPH_CONTEXT_FEATURES. They are keyed on composite identifiers so each
anchor resolves to a distinct value in the enrichment Cypher queries.
"""

from dataclasses import dataclass, field
from typing import Any

from app.graph.utils import utc_now_iso


@dataclass
class BaseNode:
    """Base node with common properties."""
    node_id: str
    label: str
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ── Coarse nodes (TPKE / RCA) ─────────────────────────────────────────────────

@dataclass
class SupplierNode(BaseNode):
    """Supplier entity node — one per Department Name. Used by TPKE/RCA."""
    label: str = "Supplier"
    supplier_id: str = ""
    supplier_name: str = ""
    supplier_reliability_score: float = 0.0
    reliability_score: float = 0.0
    supplier_delay_rate: float = 0.0
    shipping_efficiency_score: float = 0.0
    avg_delay: float = 0.0
    avg_delay_days: float = 0.0
    total_orders: int = 0
    risk_score: float = 0.0


@dataclass
class ProductNode(BaseNode):
    """Product entity node — one per Category Name."""
    label: str = "Product"
    product_id: str = ""
    category: str = ""
    rolling_7d_demand: float = 0.0
    rolling_30d_demand: float = 0.0
    demand_volatility: float = 0.0
    demand_trend: float = 0.0
    demand_trend_slope: float = 0.0
    demand_momentum: float = 0.0
    avg_spike_rate: float = 0.0
    inventory_stress: float = 0.0
    forecast_risk: float = 0.0


@dataclass
class WarehouseNode(BaseNode):
    """Warehouse entity node — one per Order City."""
    label: str = "Warehouse"
    warehouse_id: str = ""
    city: str = ""
    region: str = ""
    location_region: str = ""
    stock_coverage_ratio: float = 0.0
    inventory_stress_index: float = 0.0
    avg_inventory_stress: float = 0.0
    days_until_reorder: float = 0.0
    avg_days_to_reorder: float = 0.0
    avg_coverage_ratio: float = 0.0
    warehouse_risk: float = 0.0


@dataclass
class ShipmentNode(BaseNode):
    """Shipment entity node — one per Shipping Mode. Used by TPKE/RCA."""
    label: str = "Shipment"
    shipment_id: str = ""
    shipping_mode: str = ""
    scheduled_days: float = 0.0
    actual_days: float = 0.0
    shipping_delay: float = 0.0
    shipping_efficiency_score: float = 0.0
    late_delivery_rate: float = 0.0


@dataclass
class CustomerNode(BaseNode):
    label: str = "Customer"
    customer_id: str = ""
    segment: str = ""
    region: str = ""
    total_orders: int = 0
    avg_order_value: float = 0.0
    profit_margin: float = 0.0


@dataclass
class OrderNode(BaseNode):
    label: str = "Order"
    order_id: str = ""
    order_date: str = ""
    order_value: float = 0.0
    order_quantity: int = 0
    profit: float = 0.0
    risk_score: float = 0.0


@dataclass
class TemporalPeriodNode(BaseNode):
    """Temporal period node representing a calendar month or day-type.

    Named TemporalPeriod (not CalendarEvent) because these nodes represent
    recurring time periods synthesised from order dates, not external calendar
    events from a dataset like M5. DataCo is the sole data source.
    """
    label: str = "TemporalPeriod"
    event_id: str = ""
    event_name: str = ""
    event_type: str = ""
    is_holiday: bool = False


# Backward-compatible alias so existing imports keep working
CalendarEventNode = TemporalPeriodNode


# ── Fine-grained enrichment nodes ─────────────────────────────────────────────
# Keyed on composite identifiers. Properties computed on training slice only
# and tagged with window_end so _Q_WINDOW_CHECK can detect leakage.

@dataclass
class SupplierRouteNode(BaseNode):
    """
    One node per (Department Name, Category Name, Order Region).
    Target cardinality on DataCo: 714.
    Carries reliability_score used by _Q_SUPPLIER in enrichment.
    """
    label: str = "SupplierRoute"
    dept: str = ""
    category: str = ""
    region: str = ""
    reliability_score: float = 0.0
    hist_late_rate: float = 0.0
    lead_time_mean: float = 0.0
    lead_time_std: float = 0.0
    order_volume: int = 0
    window_end: str = ""   # ISO date of training slice cutoff — for leakage check
    computed_from_window: bool = True


@dataclass
class RouteNode(BaseNode):
    """
    One node per (Shipping Mode, Order Region, Order Country).
    Target cardinality on DataCo: 572.
    Carries avg_delay used by _Q_SHIPPING in enrichment.
    """
    label: str = "Route"
    shipping_mode: str = ""
    order_region: str = ""
    order_country: str = ""
    avg_delay: float = 0.0
    late_delivery_rate: float = 0.0
    order_volume: int = 0
    window_end: str = ""
    computed_from_window: bool = True


@dataclass
class InventoryNode(BaseNode):
    """
    One node per (Category Name, Order Region).
    Target cardinality on DataCo: 691.
    Carries avg_inventory_stress used by _Q_INVENTORY in enrichment.
    """
    label: str = "Inventory"
    category: str = ""
    region: str = ""
    avg_inventory_stress: float = 0.0
    avg_late_rate: float = 0.0
    order_volume: int = 0
    window_end: str = ""
    computed_from_window: bool = True

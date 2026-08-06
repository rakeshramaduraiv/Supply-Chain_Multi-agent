"""
AMASCI Graph Node Definitions
================================
Node type schemas and property definitions for all supply chain entities.
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


@dataclass
class SupplierNode(BaseNode):
    """Supplier entity node."""
    label: str = "Supplier"
    supplier_id: str = ""
    supplier_name: str = ""
    supplier_reliability_score: float = 0.0
    reliability_score: float = 0.0     # alias read by get_agent_context() Cypher
    supplier_delay_rate: float = 0.0
    shipping_efficiency_score: float = 0.0
    avg_delay: float = 0.0
    avg_delay_days: float = 0.0        # alias read by get_agent_context() Cypher
    total_orders: int = 0
    risk_score: float = 0.0


@dataclass
class ProductNode(BaseNode):
    """Product entity node."""
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
    """Warehouse entity node."""
    label: str = "Warehouse"
    warehouse_id: str = ""
    city: str = ""
    region: str = ""
    location_region: str = ""          # alias read by get_agent_context() Cypher
    stock_coverage_ratio: float = 0.0
    inventory_stress_index: float = 0.0
    avg_inventory_stress: float = 0.0  # alias read by get_agent_context() Cypher
    days_until_reorder: float = 0.0
    avg_days_to_reorder: float = 0.0   # alias read by get_agent_context() Cypher
    avg_coverage_ratio: float = 0.0
    warehouse_risk: float = 0.0


@dataclass
class ShipmentNode(BaseNode):
    """Shipment entity node."""
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
    """Customer entity node."""
    label: str = "Customer"
    customer_id: str = ""
    segment: str = ""
    region: str = ""
    total_orders: int = 0
    avg_order_value: float = 0.0
    profit_margin: float = 0.0


@dataclass
class OrderNode(BaseNode):
    """Order entity node."""
    label: str = "Order"
    order_id: str = ""
    order_date: str = ""
    order_value: float = 0.0
    order_quantity: int = 0
    profit: float = 0.0
    risk_score: float = 0.0


@dataclass
class CalendarEventNode(BaseNode):
    """Calendar event node for temporal context."""
    label: str = "CalendarEvent"
    event_id: str = ""
    event_name: str = ""
    event_type: str = ""
    is_holiday: bool = False

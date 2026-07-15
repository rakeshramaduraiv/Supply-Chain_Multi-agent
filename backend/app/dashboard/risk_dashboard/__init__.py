"""
AMASCI Risk Dashboard
========================
Risk analytics across all supply chain dimensions.
"""

from typing import Any
from app.dashboard.utils import format_card, risk_label, utc_now_iso


class RiskDashboard:
    """Generates risk analytics for the dashboard."""

    def generate(self, ml_metrics: dict[str, Any], rca_stats: dict[str, Any] | None = None) -> dict[str, Any]:
        rca = rca_stats or {}

        supplier_risk = ml_metrics.get("avg_supplier_risk", 0.3)
        warehouse_risk = ml_metrics.get("avg_warehouse_risk", 0.2)
        shipment_risk = ml_metrics.get("avg_late_delivery_rate", 0.4)
        inventory_risk = ml_metrics.get("avg_inventory_stress", 0.25)
        customer_risk = ml_metrics.get("avg_customer_risk", 0.15)
        product_risk = ml_metrics.get("avg_product_risk", 0.2)
        regional_risk = ml_metrics.get("avg_regional_risk", 0.2)
        overall = (supplier_risk + warehouse_risk + shipment_risk + inventory_risk) / 4.0

        cards = [
            format_card("Enterprise Risk", f"{overall:.0%}", trend="stable"),
            format_card("Supplier Risk", f"{supplier_risk:.0%}"),
            format_card("Warehouse Risk", f"{warehouse_risk:.0%}"),
            format_card("Shipment Risk", f"{shipment_risk:.0%}"),
            format_card("Inventory Risk", f"{inventory_risk:.0%}"),
        ]

        risk_breakdown = [
            {"category": "Supplier", "score": round(supplier_risk, 4), "level": risk_label(supplier_risk)},
            {"category": "Warehouse", "score": round(warehouse_risk, 4), "level": risk_label(warehouse_risk)},
            {"category": "Shipment", "score": round(shipment_risk, 4), "level": risk_label(shipment_risk)},
            {"category": "Inventory", "score": round(inventory_risk, 4), "level": risk_label(inventory_risk)},
            {"category": "Customer", "score": round(customer_risk, 4), "level": risk_label(customer_risk)},
            {"category": "Product", "score": round(product_risk, 4), "level": risk_label(product_risk)},
            {"category": "Regional", "score": round(regional_risk, 4), "level": risk_label(regional_risk)},
        ]
        risk_breakdown.sort(key=lambda x: x["score"], reverse=True)

        return {
            "cards": cards,
            "overall_risk": round(overall, 4),
            "overall_level": risk_label(overall),
            "breakdown": risk_breakdown,
            "rca_summary": {
                "total_analyses": rca.get("total_analyses", 0),
                "avg_duration_ms": rca.get("avg_duration_ms", 0.0),
            },
            "generated_at": utc_now_iso(),
        }

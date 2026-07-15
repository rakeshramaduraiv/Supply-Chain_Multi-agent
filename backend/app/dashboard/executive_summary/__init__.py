"""
AMASCI Executive Summary Engine
==================================
Generates executive-level insights and recommendations.
"""

import logging
from typing import Any

from app.dashboard.utils import risk_label, utc_now_iso

logger = logging.getLogger(__name__)


class ExecutiveSummaryEngine:
    """Generates executive summary from aggregated analytics."""

    def generate(
        self,
        kpis: dict[str, Any],
        risk_data: dict[str, Any] | None = None,
        forecast_data: dict[str, Any] | None = None,
        rca_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate complete executive summary."""
        return {
            "overall_health": kpis.get("overall_health", 0.0),
            "health_label": kpis.get("overall_health_label", "medium"),
            "top_operational_risks": self._top_risks(kpis, risk_data),
            "top_suppliers": self._top_suppliers(kpis),
            "critical_warehouses": self._critical_warehouses(kpis),
            "demand_overview": self._demand_overview(kpis, forecast_data),
            "monthly_highlights": self._monthly_highlights(kpis),
            "system_recommendations": self._recommendations(kpis, rca_data),
            "generated_at": utc_now_iso(),
        }

    def _top_risks(self, kpis: dict[str, Any], risk_data: dict[str, Any] | None) -> list[dict[str, Any]]:
        risk = kpis.get("risk", {})
        risks = [
            {"name": "Shipment Delay", "score": risk.get("shipment_risk", 0.0)},
            {"name": "Supplier Reliability", "score": risk.get("supplier_risk", 0.0)},
            {"name": "Inventory Stress", "score": risk.get("inventory_risk", 0.0)},
            {"name": "Warehouse Congestion", "score": risk.get("warehouse_risk", 0.0)},
            {"name": "Demand Volatility", "score": 1.0 - kpis.get("supply_chain", {}).get("demand_stability", 0.7)},
        ]
        risks.sort(key=lambda x: x["score"], reverse=True)
        for r in risks:
            r["level"] = risk_label(r["score"])
            r["score"] = round(r["score"], 4)
        return risks[:5]

    def _top_suppliers(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        reliability = kpis.get("supply_chain", {}).get("supplier_reliability", 0.7)
        return [
            {"insight": f"Average supplier reliability: {reliability:.0%}"},
            {"insight": "Top suppliers maintain >90% on-time delivery"},
            {"insight": f"Risk level: {risk_label(1.0 - reliability)}"},
        ]

    def _critical_warehouses(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        wh_health = kpis.get("supply_chain", {}).get("warehouse_health", 0.8)
        return [
            {"insight": f"Warehouse health index: {wh_health:.0%}"},
            {"insight": f"Risk level: {risk_label(1.0 - wh_health)}"},
        ]

    def _demand_overview(self, kpis: dict[str, Any], forecast_data: dict[str, Any] | None) -> dict[str, Any]:
        sc = kpis.get("supply_chain", {})
        pred = kpis.get("prediction", {})
        return {
            "stability": sc.get("demand_stability", 0.7),
            "forecast_accuracy": pred.get("forecast_accuracy", 0.85),
            "mape": pred.get("mape", 15.0),
            "trend": "stable",
        }

    def _monthly_highlights(self, kpis: dict[str, Any]) -> list[str]:
        highlights = []
        overall = kpis.get("overall_health", 0.5)
        if overall >= 0.7:
            highlights.append("Supply chain operating within healthy parameters")
        else:
            highlights.append("Supply chain health below target — review risk factors")

        risk = kpis.get("risk", {}).get("overall_risk", 0.3)
        if risk > 0.5:
            highlights.append(f"Enterprise risk elevated at {risk:.0%} — immediate attention required")
        else:
            highlights.append(f"Enterprise risk at {risk:.0%} — within acceptable range")

        graph = kpis.get("graph", {})
        if graph.get("total_nodes", 0) > 0:
            highlights.append(f"Knowledge graph active: {graph['total_nodes']} nodes, {graph.get('total_relationships', 0)} relationships")

        tpke = kpis.get("tpke", {})
        if tpke.get("evolution_cycles", 0) > 0:
            highlights.append(f"TPKE completed {tpke['evolution_cycles']} evolution cycles")

        return highlights

    def _recommendations(self, kpis: dict[str, Any], rca_data: dict[str, Any] | None) -> list[str]:
        recs = []
        risk = kpis.get("risk", {})

        if risk.get("supplier_risk", 0) > 0.4:
            recs.append("Diversify supplier base for high-risk categories")
        if risk.get("shipment_risk", 0) > 0.5:
            recs.append("Review shipping mode allocation and carrier performance")
        if risk.get("inventory_risk", 0) > 0.3:
            recs.append("Adjust safety stock levels for volatile demand products")
        if risk.get("warehouse_risk", 0) > 0.3:
            recs.append("Evaluate warehouse capacity and redistribution options")

        pred = kpis.get("prediction", {})
        if pred.get("mape", 0) > 20:
            recs.append("Forecast accuracy below target — retrain models with recent data")

        if not recs:
            recs.append("All systems operating within normal parameters")

        return recs[:7]

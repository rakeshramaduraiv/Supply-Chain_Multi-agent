"""
AMASCI KPI Engine
===================
Enterprise KPI computation from all system modules.
"""

import logging
from typing import Any

from app.dashboard.utils import compute_health_score, format_card, risk_label, utc_now_iso

logger = logging.getLogger(__name__)


class KPIEngine:
    """
    Computes enterprise KPIs by aggregating outputs from all modules.

    KPI Categories:
    - Supply Chain Health
    - Risk Scores
    - Forecast Accuracy
    - Graph Health
    - TPKE Evolution
    - Prediction Confidence
    """

    def compute_all_kpis(
        self,
        ml_metrics: dict[str, Any] | None = None,
        graph_stats: dict[str, Any] | None = None,
        tpke_stats: dict[str, Any] | None = None,
        rca_stats: dict[str, Any] | None = None,
        forecast_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compute all enterprise KPIs."""
        ml = ml_metrics or {}
        graph = graph_stats or {}
        tpke = tpke_stats or {}
        rca = rca_stats or {}
        forecast = forecast_metrics or {}

        supply_chain = self._compute_supply_chain_kpis(ml, forecast)
        risk = self._compute_risk_kpis(ml, rca)
        graph_health = self._compute_graph_kpis(graph)
        tpke_kpis = self._compute_tpke_kpis(tpke)
        prediction = self._compute_prediction_kpis(ml, forecast)

        overall_health = compute_health_score({
            "supply_chain": supply_chain.get("overall_health", 0.5),
            "risk_inverse": 1.0 - risk.get("overall_risk", 0.5),
            "graph": graph_health.get("graph_health", 0.5),
            "prediction": prediction.get("confidence", 0.5),
        })

        return {
            "overall_health": overall_health,
            "overall_health_label": risk_label(1.0 - overall_health),
            "supply_chain": supply_chain,
            "risk": risk,
            "graph": graph_health,
            "tpke": tpke_kpis,
            "prediction": prediction,
            "generated_at": utc_now_iso(),
        }

    def get_summary_cards(self, kpis: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate dashboard summary cards from KPIs."""
        sc = kpis.get("supply_chain", {})
        risk = kpis.get("risk", {})
        graph = kpis.get("graph", {})
        pred = kpis.get("prediction", {})

        return [
            format_card("Overall Health", f"{kpis.get('overall_health', 0):.0%}", trend="stable"),
            format_card("Supply Chain Score", f"{sc.get('overall_health', 0):.0%}"),
            format_card("Enterprise Risk", f"{risk.get('overall_risk', 0):.0%}",
                        trend="increasing" if risk.get("overall_risk", 0) > 0.5 else "stable"),
            format_card("Forecast Accuracy", f"{pred.get('accuracy', 0):.0%}"),
            format_card("Avg Delay", f"{sc.get('avg_delay', 0):.1f}", unit="days"),
            format_card("Supplier Reliability", f"{sc.get('supplier_reliability', 0):.0%}"),
            format_card("Graph Nodes", graph.get("total_nodes", 0)),
            format_card("Graph Density", f"{graph.get('density', 0):.4f}"),
            format_card("Prediction Confidence", f"{pred.get('confidence', 0):.0%}"),
        ]

    def _compute_supply_chain_kpis(self, ml: dict[str, Any], forecast: dict[str, Any]) -> dict[str, Any]:
        supplier_reliability = 1.0 - ml.get("avg_supplier_delay_rate", 0.3)
        shipping_efficiency = ml.get("avg_shipping_efficiency", 0.7)
        avg_delay = ml.get("avg_delay_days", 2.5)
        demand_stability = 1.0 - forecast.get("avg_volatility", 0.3)
        warehouse_health = 1.0 - ml.get("avg_warehouse_risk", 0.2)
        inventory_health = 1.0 - ml.get("avg_inventory_stress", 0.25)

        overall = compute_health_score({
            "supplier": supplier_reliability,
            "shipping": shipping_efficiency,
            "demand": demand_stability,
            "warehouse": warehouse_health,
            "inventory": inventory_health,
        })

        return {
            "overall_health": overall,
            "supplier_reliability": round(supplier_reliability, 4),
            "shipping_efficiency": round(shipping_efficiency, 4),
            "avg_delay": round(avg_delay, 2),
            "demand_stability": round(demand_stability, 4),
            "warehouse_health": round(warehouse_health, 4),
            "inventory_health": round(inventory_health, 4),
        }

    def _compute_risk_kpis(self, ml: dict[str, Any], rca: dict[str, Any]) -> dict[str, Any]:
        supplier_risk = ml.get("avg_supplier_risk", 0.3)
        warehouse_risk = ml.get("avg_warehouse_risk", 0.2)
        shipment_risk = ml.get("avg_late_delivery_rate", 0.4)
        inventory_risk = ml.get("avg_inventory_stress", 0.25)
        overall = (supplier_risk + warehouse_risk + shipment_risk + inventory_risk) / 4.0

        return {
            "overall_risk": round(overall, 4),
            "overall_risk_level": risk_label(overall),
            "supplier_risk": round(supplier_risk, 4),
            "warehouse_risk": round(warehouse_risk, 4),
            "shipment_risk": round(shipment_risk, 4),
            "inventory_risk": round(inventory_risk, 4),
            "rca_analyses_count": rca.get("total_analyses", 0),
        }

    def _compute_graph_kpis(self, graph: dict[str, Any]) -> dict[str, Any]:
        total_nodes = graph.get("total_nodes", 0)
        total_rels = graph.get("total_relationships", 0)
        density = graph.get("graph_density", 0.0)
        components = graph.get("connected_components", 1)

        avg_degree = (2 * total_rels) / max(total_nodes, 1)
        graph_health = min(1.0, (density * 1000 + avg_degree / 10) / 2)

        return {
            "graph_health": round(graph_health, 4),
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "density": round(density, 6),
            "avg_degree": round(avg_degree, 2),
            "connected_components": components,
        }

    def _compute_tpke_kpis(self, tpke: dict[str, Any]) -> dict[str, Any]:
        return {
            "evolution_score": tpke.get("evolution_score", 0.0),
            "edges_added": tpke.get("edges_added", 0),
            "edges_updated": tpke.get("edges_updated", 0),
            "edges_removed": tpke.get("edges_removed", 0),
            "inferred_edge_count": tpke.get("inferred_edge_count", 0),
            "avg_edge_confidence": tpke.get("avg_edge_confidence", 0.0),
            "pattern_frequency": tpke.get("pattern_frequency", 0),
            "evolution_cycles": tpke.get("evolution_cycles", 0),
            "graph_growth_rate": tpke.get("graph_growth_rate", 0.0),
            "pattern_stability": tpke.get("pattern_stability", 0.0),
        }

    def _compute_prediction_kpis(self, ml: dict[str, Any], forecast: dict[str, Any]) -> dict[str, Any]:
        accuracy = ml.get("accuracy", 0.75)
        mape = forecast.get("mape", 15.0)
        rmse = forecast.get("rmse", 0.0)
        confidence = ml.get("avg_confidence", 0.7)

        return {
            "accuracy": round(accuracy, 4),
            "mape": round(mape, 2),
            "rmse": round(rmse, 4),
            "confidence": round(confidence, 4),
            "forecast_accuracy": round(1.0 - mape / 100.0, 4) if mape < 100 else 0.0,
        }

"""
AMASCI Comparison Engine
===========================
Period-over-period and model comparison analytics.
"""

from typing import Any
from app.dashboard.utils import compute_change_pct, utc_now_iso


class ComparisonEngine:
    """
    Supports:
    - Prediction vs Actual
    - Current vs Previous period
    - Before TPKE vs After TPKE
    - Static KG vs TPKE KG
    """

    def compare_prediction_vs_actual(
        self, predictions: list[float], actuals: list[float]
    ) -> dict[str, Any]:
        if not predictions or not actuals:
            return {"error": "Insufficient data", "generated_at": utc_now_iso()}

        n = min(len(predictions), len(actuals))
        preds = predictions[:n]
        acts = actuals[:n]

        errors = [abs(p - a) for p, a in zip(preds, acts)]
        mae = sum(errors) / n
        mape = sum(e / max(abs(a), 0.001) for e, a in zip(errors, acts)) / n * 100

        return {
            "comparison_type": "prediction_vs_actual",
            "sample_size": n,
            "mae": round(mae, 4),
            "mape": round(mape, 2),
            "accuracy": round(1.0 - mape / 100, 4) if mape < 100 else 0.0,
            "avg_prediction": round(sum(preds) / n, 4),
            "avg_actual": round(sum(acts) / n, 4),
            "generated_at": utc_now_iso(),
        }

    def compare_periods(
        self, current: dict[str, float], previous: dict[str, float]
    ) -> dict[str, Any]:
        changes = {}
        for key in current:
            curr_val = current.get(key, 0.0)
            prev_val = previous.get(key, 0.0)
            changes[key] = {
                "current": round(curr_val, 4),
                "previous": round(prev_val, 4),
                "change_pct": compute_change_pct(curr_val, prev_val),
                "direction": "up" if curr_val > prev_val else "down" if curr_val < prev_val else "flat",
            }
        return {
            "comparison_type": "period_over_period",
            "metrics": changes,
            "generated_at": utc_now_iso(),
        }

    def compare_tpke_impact(
        self, before_tpke: dict[str, float], after_tpke: dict[str, float]
    ) -> dict[str, Any]:
        improvements = {}
        for key in after_tpke:
            before_val = before_tpke.get(key, 0.0)
            after_val = after_tpke.get(key, 0.0)
            improvements[key] = {
                "before": round(before_val, 4),
                "after": round(after_val, 4),
                "improvement_pct": compute_change_pct(after_val, before_val),
            }
        return {
            "comparison_type": "tpke_impact",
            "metrics": improvements,
            "generated_at": utc_now_iso(),
        }

    def compare_graph_versions(
        self, static_kg: dict[str, Any], tpke_kg: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "comparison_type": "static_vs_tpke",
            "static_kg": {
                "nodes": static_kg.get("total_nodes", 0),
                "relationships": static_kg.get("total_relationships", 0),
                "density": static_kg.get("graph_density", 0.0),
            },
            "tpke_kg": {
                "nodes": tpke_kg.get("total_nodes", 0),
                "relationships": tpke_kg.get("total_relationships", 0),
                "density": tpke_kg.get("graph_density", 0.0),
                "inferred_edges": tpke_kg.get("inferred_edge_count", 0),
            },
            "delta": {
                "node_growth": tpke_kg.get("total_nodes", 0) - static_kg.get("total_nodes", 0),
                "rel_growth": tpke_kg.get("total_relationships", 0) - static_kg.get("total_relationships", 0),
                "density_change": round(
                    tpke_kg.get("graph_density", 0.0) - static_kg.get("graph_density", 0.0), 6
                ),
            },
            "generated_at": utc_now_iso(),
        }

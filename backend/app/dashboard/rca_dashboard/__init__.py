"""
AMASCI RCA Dashboard
=======================
Root Cause Analysis analytics for the dashboard.
"""

from typing import Any
from app.dashboard.utils import format_card, utc_now_iso


class RCADashboard:
    """Generates RCA analytics for the dashboard."""

    def generate(self, rca_stats: dict[str, Any], rca_history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        history = rca_history or []

        total = rca_stats.get("total_analyses", 0)
        avg_duration = rca_stats.get("avg_duration_ms", 0.0)
        by_type = rca_stats.get("analyses_by_type", {})

        cards = [
            format_card("Total Analyses", total),
            format_card("Avg Duration", f"{avg_duration:.0f}", unit="ms"),
        ]

        type_distribution = [
            {"rca_type": rca_type, "count": count}
            for rca_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True)
        ]

        # Extract top root causes from history
        cause_freq: dict[str, int] = {}
        affected_regions: set[str] = set()
        affected_suppliers: set[str] = set()
        affected_products: set[str] = set()

        for record in history:
            report = record if isinstance(record, dict) else {}
            primary = report.get("primary_root_cause", {})
            if primary and primary.get("label"):
                key = f"{primary.get('label')}:{primary.get('node_id', '')[:8]}"
                cause_freq[key] = cause_freq.get(key, 0) + 1

            affected = report.get("affected_entities", {})
            for s in affected.get("suppliers", []):
                affected_suppliers.add(s.get("node_id", ""))
            for p in affected.get("products", []):
                affected_products.add(p.get("node_id", ""))
            for r in affected.get("regions", []):
                affected_regions.add(r)

        top_causes = sorted(cause_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "cards": cards,
            "metrics": {
                "total_analyses": total,
                "avg_duration_ms": round(avg_duration, 2),
            },
            "type_distribution": type_distribution,
            "top_root_causes": [{"cause": c[0], "frequency": c[1]} for c in top_causes],
            "affected_summary": {
                "suppliers": len(affected_suppliers),
                "products": len(affected_products),
                "regions": len(affected_regions),
            },
            "recent_analyses": history[-5:],
            "generated_at": utc_now_iso(),
        }

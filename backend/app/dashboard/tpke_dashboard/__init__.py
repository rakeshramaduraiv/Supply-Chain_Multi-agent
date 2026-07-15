"""
AMASCI TPKE Dashboard
========================
TPKE evolution analytics for the dashboard.
"""

from typing import Any
from app.dashboard.utils import format_card, utc_now_iso


class TPKEDashboard:
    """Generates TPKE evolution analytics for the dashboard."""

    def generate(self, tpke_stats: dict[str, Any], tpke_history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        history = tpke_history or []

        edges_added = tpke_stats.get("edges_added", 0)
        edges_updated = tpke_stats.get("edges_updated", 0)
        edges_removed = tpke_stats.get("edges_removed", 0)
        avg_confidence = tpke_stats.get("avg_edge_confidence", 0.0)
        evolution_cycles = tpke_stats.get("evolution_cycles", 0)
        pattern_freq = tpke_stats.get("pattern_frequency", 0)
        growth_rate = tpke_stats.get("graph_growth_rate", 0.0)
        stability = tpke_stats.get("pattern_stability", 0.0)

        cards = [
            format_card("Edges Added", edges_added),
            format_card("Edges Updated", edges_updated),
            format_card("Edges Removed", edges_removed),
            format_card("Avg Confidence", f"{avg_confidence:.2f}"),
            format_card("Evolution Cycles", evolution_cycles),
            format_card("Pattern Frequency", pattern_freq),
            format_card("Growth Rate", f"{growth_rate:.2%}"),
            format_card("Pattern Stability", f"{stability:.2f}"),
        ]

        return {
            "cards": cards,
            "metrics": {
                "edges_added": edges_added,
                "edges_updated": edges_updated,
                "edges_removed": edges_removed,
                "avg_edge_confidence": round(avg_confidence, 4),
                "evolution_cycles": evolution_cycles,
                "pattern_frequency": pattern_freq,
                "graph_growth_rate": round(growth_rate, 4),
                "pattern_stability": round(stability, 4),
                "inferred_edge_count": tpke_stats.get("inferred_edge_count", 0),
            },
            "history": history[-20:],
            "generated_at": utc_now_iso(),
        }

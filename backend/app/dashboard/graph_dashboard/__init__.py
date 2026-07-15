"""
AMASCI Graph Dashboard
=========================
Knowledge Graph analytics for the dashboard.
"""

from typing import Any
from app.dashboard.utils import format_card, utc_now_iso


class GraphDashboard:
    """Generates Knowledge Graph analytics for the dashboard."""

    def generate(self, graph_stats: dict[str, Any]) -> dict[str, Any]:
        total_nodes = graph_stats.get("total_nodes", 0)
        total_rels = graph_stats.get("total_relationships", 0)
        density = graph_stats.get("graph_density", 0.0)
        components = graph_stats.get("connected_components", 0)
        node_counts = graph_stats.get("node_counts", {})
        rel_counts = graph_stats.get("relationship_counts", {})

        avg_degree = (2 * total_rels) / max(total_nodes, 1)

        cards = [
            format_card("Total Nodes", total_nodes),
            format_card("Total Relationships", total_rels),
            format_card("Graph Density", f"{density:.6f}"),
            format_card("Avg Degree", f"{avg_degree:.2f}"),
            format_card("Connected Components", components),
        ]

        node_distribution = [
            {"label": label, "count": count}
            for label, count in sorted(node_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        rel_distribution = [
            {"type": rel_type, "count": count}
            for rel_type, count in sorted(rel_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "cards": cards,
            "metrics": {
                "total_nodes": total_nodes,
                "total_relationships": total_rels,
                "density": round(density, 6),
                "avg_degree": round(avg_degree, 2),
                "connected_components": components,
                "avg_edge_weight": graph_stats.get("avg_edge_weight", 0.0),
            },
            "node_distribution": node_distribution,
            "relationship_distribution": rel_distribution,
            "generated_at": utc_now_iso(),
        }

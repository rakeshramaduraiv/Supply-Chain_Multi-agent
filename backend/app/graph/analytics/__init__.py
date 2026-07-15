"""
AMASCI Graph Analytics
=======================
Structural analytics: centrality, PageRank, connected components, density, shortest path.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)


@dataclass
class GraphStatistics:
    """Aggregate graph statistics."""
    total_nodes: int = 0
    total_relationships: int = 0
    node_counts: dict[str, int] = field(default_factory=dict)
    relationship_counts: dict[str, int] = field(default_factory=dict)
    graph_density: float = 0.0
    connected_components: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "total_relationships": self.total_relationships,
            "node_counts": self.node_counts,
            "relationship_counts": self.relationship_counts,
            "graph_density": round(self.graph_density, 6),
            "connected_components": self.connected_components,
        }


class GraphAnalytics:
    """
    Graph analytics engine using Cypher queries.

    Provides:
    - Node/relationship counts
    - Degree centrality
    - PageRank (via GDS or approximation)
    - Connected components
    - Shortest path
    - Graph density
    """

    def __init__(self, connection: Neo4jConnectionManager):
        self._conn = connection

    async def get_statistics(self) -> GraphStatistics:
        """Compute comprehensive graph statistics."""
        stats = GraphStatistics()

        # Total nodes
        records = await self._conn.execute_query("MATCH (n) RETURN count(n) AS cnt")
        stats.total_nodes = records[0]["cnt"] if records else 0

        # Total relationships
        records = await self._conn.execute_query("MATCH ()-[r]->() RETURN count(r) AS cnt")
        stats.total_relationships = records[0]["cnt"] if records else 0

        # Node counts by label
        records = await self._conn.execute_query("""
            CALL db.labels() YIELD label
            CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) AS cnt', {}) YIELD value
            RETURN label, value.cnt AS cnt
        """)
        if not records:
            # Fallback without APOC
            labels = ["Supplier", "Product", "Warehouse", "Shipment", "Customer", "Order", "CalendarEvent"]
            for lbl in labels:
                r = await self._conn.execute_query(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
                if r:
                    stats.node_counts[lbl] = r[0]["cnt"]
        else:
            for r in records:
                stats.node_counts[r["label"]] = r["cnt"]

        # Relationship counts by type
        records = await self._conn.execute_query("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS cnt
        """)
        for r in records:
            stats.relationship_counts[r["rel_type"]] = r["cnt"]

        # Graph density: 2*E / (N*(N-1)) for directed graph: E / (N*(N-1))
        n = stats.total_nodes
        e = stats.total_relationships
        if n > 1:
            stats.graph_density = e / (n * (n - 1))

        # Connected components (weakly connected)
        stats.connected_components = await self._count_connected_components()

        return stats

    async def get_node_count(self, label: str | None = None) -> int:
        """Get node count, optionally filtered by label."""
        if label:
            query = f"MATCH (n:{label}) RETURN count(n) AS cnt"
        else:
            query = "MATCH (n) RETURN count(n) AS cnt"
        records = await self._conn.execute_query(query)
        return records[0]["cnt"] if records else 0

    async def get_relationship_count(self, rel_type: str | None = None) -> int:
        """Get relationship count, optionally filtered by type."""
        if rel_type:
            query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt"
        else:
            query = "MATCH ()-[r]->() RETURN count(r) AS cnt"
        records = await self._conn.execute_query(query)
        return records[0]["cnt"] if records else 0

    async def degree_centrality(self, label: str, top_n: int = 10) -> list[dict[str, Any]]:
        """Compute degree centrality for nodes of a given label."""
        query = f"""
            MATCH (n:{label})
            OPTIONAL MATCH (n)-[r]-()
            WITH n, count(r) AS degree
            RETURN n.node_id AS node_id, n.{self._name_property(label)} AS name, degree
            ORDER BY degree DESC
            LIMIT $top_n
        """
        records = await self._conn.execute_query(query, {"top_n": top_n})

        # Normalize
        max_degree = records[0]["degree"] if records else 1
        max_degree = max(max_degree, 1)

        return [
            {
                "node_id": r["node_id"],
                "name": r["name"],
                "degree": r["degree"],
                "centrality": round(r["degree"] / max_degree, 4),
            }
            for r in records
        ]

    async def pagerank(self, label: str, top_n: int = 10) -> list[dict[str, Any]]:
        """
        Approximate PageRank using iterative Cypher.

        Uses a simplified 3-iteration approach without GDS plugin.
        """
        # Initialize scores
        await self._conn.execute_write(f"""
            MATCH (n:{label})
            SET n._pr = 1.0 / toFloat(count {{ MATCH (m:{label}) RETURN m }})
        """)

        # 3 iterations of simplified PageRank
        damping = 0.85
        for _ in range(3):
            await self._conn.execute_write(f"""
                MATCH (n:{label})
                OPTIONAL MATCH (m)-[]->(n)
                WITH n, collect(m) AS inbound
                OPTIONAL MATCH (m2)-[]->(n) WHERE m2:{label}
                WITH n, CASE WHEN size(inbound) = 0 THEN 0.0
                     ELSE {damping} * reduce(s = 0.0, m IN inbound |
                         s + coalesce(m._pr, 0.0) / toFloat(
                             CASE WHEN size([(m)-[]->() | 1]) = 0 THEN 1
                             ELSE size([(m)-[]->() | 1]) END
                         ))
                     END + (1.0 - {damping}) AS new_pr
                SET n._pr = new_pr
            """)

        # Fetch results
        query = f"""
            MATCH (n:{label})
            WHERE n._pr IS NOT NULL
            RETURN n.node_id AS node_id, n.{self._name_property(label)} AS name, n._pr AS score
            ORDER BY n._pr DESC
            LIMIT $top_n
        """
        records = await self._conn.execute_query(query, {"top_n": top_n})

        # Cleanup temp property
        await self._conn.execute_write(f"MATCH (n:{label}) REMOVE n._pr")

        return [
            {"node_id": r["node_id"], "name": r["name"], "pagerank": round(r["score"], 6)}
            for r in records
        ]

    async def shortest_path(
        self, source_id: str, target_id: str, max_hops: int = 5
    ) -> list[dict[str, Any]]:
        """Find shortest path between two nodes."""
        query = """
            MATCH (a {node_id: $source_id}), (b {node_id: $target_id})
            MATCH path = shortestPath((a)-[*..%d]-(b))
            RETURN [n IN nodes(path) | {node_id: n.node_id, label: labels(n)[0]}] AS nodes,
                   [r IN relationships(path) | {type: type(r), strength: r.relationship_strength}] AS rels,
                   length(path) AS hops
        """ % max_hops
        records = await self._conn.execute_query(query, {
            "source_id": source_id,
            "target_id": target_id,
        })
        return records if records else []

    async def _count_connected_components(self) -> int:
        """Count weakly connected components using BFS traversal."""
        query = """
            MATCH (n)
            WITH collect(n) AS nodes
            UNWIND nodes AS start
            MATCH path = (start)-[*0..]-(connected)
            WITH start, collect(DISTINCT connected) AS component
            WITH collect(component) AS all_components
            RETURN size(all_components) AS components
        """
        try:
            records = await self._conn.execute_query(query)
            return records[0]["components"] if records else 0
        except Exception:
            # Fallback: simple estimation
            records = await self._conn.execute_query("""
                MATCH (n) WHERE NOT (n)--()
                RETURN count(n) AS orphans
            """)
            orphans = records[0]["orphans"] if records else 0
            return orphans + 1  # At least 1 connected component + orphans

    def _name_property(self, label: str) -> str:
        """Get the display name property for a label."""
        mapping = {
            "Supplier": "supplier_name",
            "Product": "category",
            "Warehouse": "city",
            "Shipment": "shipping_mode",
            "Customer": "customer_id",
            "Order": "order_id",
            "CalendarEvent": "event_name",
        }
        return mapping.get(label, "node_id")

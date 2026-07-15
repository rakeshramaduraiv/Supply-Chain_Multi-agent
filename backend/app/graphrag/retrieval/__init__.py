"""
AMASCI GraphRAG Retrieval Engine
==================================
Entity, relationship, subgraph, neighborhood, shortest path, and risk retrieval.
"""

import logging
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graphrag.memory import get_context_cache
from app.graphrag.utils import PerformanceTimer, generate_context_id

logger = logging.getLogger(__name__)


class RetrievalEngine:
    """
    Graph retrieval engine for GraphRAG pipeline.

    Provides:
    - Entity retrieval (single node with properties)
    - Relationship retrieval (edges for a node)
    - Subgraph retrieval (ego network)
    - Neighborhood expansion (configurable hops)
    - Shortest path retrieval
    - Top-K connected nodes
    - Risk neighborhood extraction
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()
        self._cache = get_context_cache()

    async def retrieve_entity(self, node_id: str, label: str | None = None) -> dict[str, Any] | None:
        """Retrieve a single entity with all properties."""
        cache_key = f"entity:{node_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        with PerformanceTimer("retrieve_entity"):
            if label:
                query = f"""
                    MATCH (n:{label} {{node_id: $node_id}})
                    RETURN n {{.*, _label: labels(n)[0]}} AS entity
                """
            else:
                query = """
                    MATCH (n {node_id: $node_id})
                    RETURN n {.*, _label: labels(n)[0]} AS entity
                """
            records = await self._conn.execute_query(query, {"node_id": node_id})

        if not records:
            return None

        result = records[0]["entity"]
        self._cache.set(cache_key, result)
        return result

    async def retrieve_relationships(
        self, node_id: str, label: str | None = None, direction: str = "both"
    ) -> list[dict[str, Any]]:
        """Retrieve all relationships for a node."""
        cache_key = f"rels:{node_id}:{direction}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        with PerformanceTimer("retrieve_relationships"):
            match_clause = f"(n:{label} {{node_id: $node_id}})" if label else "(n {node_id: $node_id})"

            if direction == "outgoing":
                query = f"""
                    MATCH {match_clause}-[r]->(m)
                    RETURN type(r) AS rel_type, r {{.*}} AS properties,
                           m.node_id AS target_id, labels(m)[0] AS target_label,
                           m {{.*}} AS target_props
                """
            elif direction == "incoming":
                query = f"""
                    MATCH (m)-[r]->{match_clause}
                    RETURN type(r) AS rel_type, r {{.*}} AS properties,
                           m.node_id AS source_id, labels(m)[0] AS source_label,
                           m {{.*}} AS source_props
                """
            else:
                query = f"""
                    MATCH {match_clause}-[r]-(m)
                    RETURN type(r) AS rel_type, r {{.*}} AS properties,
                           m.node_id AS connected_id, labels(m)[0] AS connected_label,
                           m {{.*}} AS connected_props,
                           CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END AS direction
                """
            records = await self._conn.execute_query(query, {"node_id": node_id})

        self._cache.set(cache_key, records)
        return records

    async def retrieve_subgraph(
        self, node_id: str, hops: int = 2, limit: int = 100
    ) -> dict[str, Any]:
        """Retrieve ego-network subgraph around a node."""
        cache_key = f"subgraph:{node_id}:{hops}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        with PerformanceTimer(f"retrieve_subgraph(hops={hops})"):
            query = f"""
                MATCH (center {{node_id: $node_id}})
                OPTIONAL MATCH path = (center)-[*1..{hops}]-(neighbor)
                WHERE neighbor <> center
                WITH center, collect(DISTINCT neighbor) AS neighbors,
                     collect(DISTINCT relationships(path)) AS all_rels
                RETURN center {{.*, _label: labels(center)[0]}} AS center_node,
                       [n IN neighbors[0..$limit] | n {{.*, _label: labels(n)[0]}}] AS neighbors,
                       size(neighbors) AS total_neighbors
            """
            records = await self._conn.execute_query(
                query, {"node_id": node_id, "limit": limit}
            )

        if not records:
            result = {"center_node": None, "neighbors": [], "edges": [], "total_neighbors": 0}
        else:
            center_node = records[0]["center_node"]
            neighbors = records[0]["neighbors"]
            total = records[0]["total_neighbors"]

            # Fetch edges between center and neighbors
            neighbor_ids = [n.get("node_id") for n in neighbors if n.get("node_id")]
            edges = await self._retrieve_edges_between(node_id, neighbor_ids)

            result = {
                "center_node": center_node,
                "neighbors": neighbors,
                "edges": edges,
                "total_neighbors": total,
            }

        self._cache.set(cache_key, result)
        return result

    async def retrieve_neighborhood(
        self, node_id: str, hops: int = 1, label_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Expand neighborhood with optional label filter."""
        with PerformanceTimer(f"retrieve_neighborhood(hops={hops})"):
            label_where = f"AND labels(neighbor)[0] = '{label_filter}'" if label_filter else ""
            query = f"""
                MATCH (center {{node_id: $node_id}})
                MATCH (center)-[*1..{hops}]-(neighbor)
                WHERE neighbor <> center {label_where}
                RETURN DISTINCT neighbor {{.*, _label: labels(neighbor)[0]}} AS node
                LIMIT 200
            """
            records = await self._conn.execute_query(query, {"node_id": node_id})
        return [r["node"] for r in records]

    async def retrieve_shortest_path(
        self, source_id: str, target_id: str, max_hops: int = 6
    ) -> dict[str, Any]:
        """Find shortest path between two nodes."""
        with PerformanceTimer("retrieve_shortest_path"):
            query = """
                MATCH (a {node_id: $source_id}), (b {node_id: $target_id})
                MATCH path = shortestPath((a)-[*..%d]-(b))
                RETURN
                    [n IN nodes(path) | {node_id: n.node_id, label: labels(n)[0], props: n {.*}}] AS path_nodes,
                    [r IN relationships(path) | {type: type(r), props: r {.*}}] AS path_edges,
                    length(path) AS hops
            """ % max_hops
            records = await self._conn.execute_query(
                query, {"source_id": source_id, "target_id": target_id}
            )

        if not records:
            return {"path_nodes": [], "path_edges": [], "hops": -1, "connected": False}

        result = records[0]
        result["connected"] = True
        return result

    async def retrieve_top_k_connected(
        self, node_id: str, k: int = 10, rel_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve top-K most connected neighbors by relationship strength."""
        with PerformanceTimer("retrieve_top_k_connected"):
            rel_filter = f":{rel_type}" if rel_type else ""
            query = f"""
                MATCH (center {{node_id: $node_id}})-[r{rel_filter}]-(neighbor)
                WITH neighbor, r,
                     coalesce(r.relationship_strength, r.weight, 1.0) AS strength
                RETURN neighbor {{.*, _label: labels(neighbor)[0]}} AS node,
                       type(r) AS rel_type,
                       strength
                ORDER BY strength DESC
                LIMIT $k
            """
            records = await self._conn.execute_query(query, {"node_id": node_id, "k": k})
        return records

    async def retrieve_risk_neighborhood(
        self, node_id: str, risk_threshold: float = 0.5, hops: int = 2
    ) -> dict[str, Any]:
        """Extract nodes in neighborhood with risk above threshold."""
        with PerformanceTimer("retrieve_risk_neighborhood"):
            query = f"""
                MATCH (center {{node_id: $node_id}})
                MATCH (center)-[*1..{hops}]-(neighbor)
                WHERE neighbor <> center
                  AND (coalesce(neighbor.risk_score, 0) >= $threshold
                       OR coalesce(neighbor.late_delivery_rate, 0) >= $threshold
                       OR coalesce(neighbor.warehouse_risk, 0) >= $threshold
                       OR coalesce(neighbor.forecast_risk, 0) >= $threshold)
                RETURN neighbor {{.*, _label: labels(neighbor)[0]}} AS node,
                       coalesce(neighbor.risk_score, neighbor.late_delivery_rate,
                                neighbor.warehouse_risk, neighbor.forecast_risk, 0) AS risk_value
                ORDER BY risk_value DESC
                LIMIT 50
            """
            records = await self._conn.execute_query(
                query, {"node_id": node_id, "threshold": risk_threshold}
            )

        risk_nodes = [r["node"] for r in records]
        risk_values = [r["risk_value"] for r in records]
        avg_risk = sum(risk_values) / len(risk_values) if risk_values else 0.0

        return {
            "center_id": node_id,
            "risk_nodes": risk_nodes,
            "risk_node_count": len(risk_nodes),
            "avg_neighborhood_risk": round(avg_risk, 4),
            "max_neighborhood_risk": max(risk_values) if risk_values else 0.0,
            "hops": hops,
            "threshold": risk_threshold,
        }

    async def _retrieve_edges_between(
        self, center_id: str, neighbor_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Retrieve edges between center and a set of neighbors."""
        if not neighbor_ids:
            return []
        query = """
            MATCH (center {node_id: $center_id})-[r]-(neighbor)
            WHERE neighbor.node_id IN $neighbor_ids
            RETURN center.node_id AS source_id,
                   neighbor.node_id AS target_id,
                   type(r) AS rel_type,
                   r {.*} AS properties
        """
        records = await self._conn.execute_query(
            query, {"center_id": center_id, "neighbor_ids": neighbor_ids}
        )
        return records

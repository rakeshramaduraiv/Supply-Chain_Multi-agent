"""
AMASCI RCA Graph Traversal Engine
====================================
BFS, DFS, shortest path, weighted shortest path, k-hop, multi-hop traversal.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.rca.utils import PerformanceTimer, MAX_TRAVERSAL_DEPTH

logger = logging.getLogger(__name__)


@dataclass
class TraversalNode:
    """A node encountered during graph traversal."""
    node_id: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    depth: int = 0
    parent_id: str | None = None
    edge_type: str = ""
    edge_weight: float = 1.0


@dataclass
class TraversalResult:
    """Result of a graph traversal operation."""
    source_id: str
    traversal_type: str
    visited_nodes: list[TraversalNode] = field(default_factory=list)
    paths: list[list[TraversalNode]] = field(default_factory=list)
    total_visited: int = 0
    max_depth_reached: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "traversal_type": self.traversal_type,
            "visited_nodes": [
                {
                    "node_id": n.node_id,
                    "label": n.label,
                    "depth": n.depth,
                    "parent_id": n.parent_id,
                    "edge_type": n.edge_type,
                    "edge_weight": n.edge_weight,
                    "properties": n.properties,
                }
                for n in self.visited_nodes
            ],
            "paths": [
                [{"node_id": n.node_id, "label": n.label, "depth": n.depth} for n in path]
                for path in self.paths
            ],
            "total_visited": self.total_visited,
            "max_depth_reached": self.max_depth_reached,
            "duration_ms": round(self.duration_ms, 2),
        }


class GraphTraversalEngine:
    """
    Graph traversal engine for RCA.

    Provides:
    - Breadth-First Search (BFS)
    - Depth-First Search (DFS)
    - Shortest Path
    - Weighted Shortest Path
    - K-Hop Traversal
    - Multi-Hop Traversal (directed)
    """

    # Issue #15: Trust weights by relationship type.
    # Static edges (from data) = 1.0; TPKE inferred = 0.6 (probabilistic).
    EDGE_TRUST_WEIGHTS: dict[str, float] = {
        "SUPPLIES":      1.0,
        "STORED_IN":     1.0,
        "SHIPS_VIA":     1.0,
        "DELIVERED_TO":  1.0,
        "PLACED":        1.0,
        "CONTAINS":      1.0,
        "INFLUENCES":    0.9,
        "TPKE_INFERRED": 0.6,
    }

    @classmethod
    def edge_trust(cls, edge_type: str) -> float:
        """Return trust weight for a relationship type (Issue #15)."""
        return cls.EDGE_TRUST_WEIGHTS.get(edge_type, 0.5)

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def bfs(
        self, source_id: str, max_depth: int = 3, label_filter: str | None = None
    ) -> TraversalResult:
        """Breadth-first search from a source node."""
        max_depth = min(max_depth, MAX_TRAVERSAL_DEPTH)

        with PerformanceTimer("bfs") as timer:
            label_where = f"AND labels(neighbor)[0] = '{label_filter}'" if label_filter else ""
            query = f"""
                MATCH (source {{node_id: $source_id}})
                CALL {{
                    WITH source
                    MATCH path = (source)-[*1..{max_depth}]-(neighbor)
                    WHERE neighbor <> source {label_where}
                    WITH neighbor, relationships(path) AS rels, length(path) AS depth
                    RETURN DISTINCT
                        neighbor.node_id AS node_id,
                        labels(neighbor)[0] AS label,
                        neighbor {{.*}} AS properties,
                        depth,
                        type(rels[size(rels)-1]) AS edge_type,
                        coalesce(rels[size(rels)-1].relationship_strength, 1.0) AS edge_weight
                    ORDER BY depth ASC
                    LIMIT 100
                }}
                RETURN node_id, label, properties, depth, edge_type, edge_weight
            """
            records = await self._conn.execute_query(query, {"source_id": source_id})

        visited = [
            TraversalNode(
                node_id=r["node_id"],
                label=r["label"],
                properties=r["properties"],
                depth=r["depth"],
                edge_type=r["edge_type"],
                # Issue #15: multiply relationship_strength by edge trust weight
                edge_weight=r["edge_weight"] * GraphTraversalEngine.edge_trust(r["edge_type"]),
            )
            for r in records
        ]

        max_d = max((n.depth for n in visited), default=0)

        return TraversalResult(
            source_id=source_id,
            traversal_type="bfs",
            visited_nodes=visited,
            total_visited=len(visited),
            max_depth_reached=max_d,
            duration_ms=timer.duration_ms,
        )

    async def dfs(
        self, source_id: str, max_depth: int = 3, label_filter: str | None = None
    ) -> TraversalResult:
        """Depth-first search from a source node (returns deepest paths first)."""
        max_depth = min(max_depth, MAX_TRAVERSAL_DEPTH)

        with PerformanceTimer("dfs") as timer:
            label_where = f"AND labels(neighbor)[0] = '{label_filter}'" if label_filter else ""
            query = f"""
                MATCH (source {{node_id: $source_id}})
                MATCH path = (source)-[*1..{max_depth}]-(neighbor)
                WHERE neighbor <> source {label_where}
                WITH neighbor, relationships(path) AS rels, length(path) AS depth
                RETURN DISTINCT
                    neighbor.node_id AS node_id,
                    labels(neighbor)[0] AS label,
                    neighbor {{.*}} AS properties,
                    depth,
                    type(rels[size(rels)-1]) AS edge_type,
                    coalesce(rels[size(rels)-1].relationship_strength, 1.0) AS edge_weight
                ORDER BY depth DESC
                LIMIT 100
            """
            records = await self._conn.execute_query(query, {"source_id": source_id})

        visited = [
            TraversalNode(
                node_id=r["node_id"],
                label=r["label"],
                properties=r["properties"],
                depth=r["depth"],
                edge_type=r["edge_type"],
                edge_weight=r["edge_weight"],
            )
            for r in records
        ]

        max_d = max((n.depth for n in visited), default=0)

        return TraversalResult(
            source_id=source_id,
            traversal_type="dfs",
            visited_nodes=visited,
            total_visited=len(visited),
            max_depth_reached=max_d,
            duration_ms=timer.duration_ms,
        )

    async def shortest_path(
        self, source_id: str, target_id: str, max_hops: int = 6
    ) -> TraversalResult:
        """Find shortest path between two nodes."""
        with PerformanceTimer("shortest_path") as timer:
            query = """
                MATCH (a {node_id: $source_id}), (b {node_id: $target_id})
                MATCH path = shortestPath((a)-[*..%d]-(b))
                RETURN
                    [n IN nodes(path) | {
                        node_id: n.node_id,
                        label: labels(n)[0],
                        properties: n {.*}
                    }] AS path_nodes,
                    [r IN relationships(path) | {
                        type: type(r),
                        weight: coalesce(r.relationship_strength, 1.0)
                    }] AS path_edges,
                    length(path) AS hops
            """ % max_hops
            records = await self._conn.execute_query(
                query, {"source_id": source_id, "target_id": target_id}
            )

        if not records:
            return TraversalResult(
                source_id=source_id,
                traversal_type="shortest_path",
                duration_ms=timer.duration_ms,
            )

        path_nodes_raw = records[0]["path_nodes"]
        path_edges_raw = records[0]["path_edges"]

        path_nodes = []
        for i, node_data in enumerate(path_nodes_raw):
            edge_type = path_edges_raw[i]["type"] if i < len(path_edges_raw) else ""
            edge_weight = path_edges_raw[i]["weight"] if i < len(path_edges_raw) else 1.0
            path_nodes.append(TraversalNode(
                node_id=node_data["node_id"],
                label=node_data["label"],
                properties=node_data["properties"],
                depth=i,
                parent_id=path_nodes_raw[i - 1]["node_id"] if i > 0 else None,
                edge_type=edge_type,
                edge_weight=edge_weight,
            ))

        return TraversalResult(
            source_id=source_id,
            traversal_type="shortest_path",
            visited_nodes=path_nodes,
            paths=[path_nodes],
            total_visited=len(path_nodes),
            max_depth_reached=records[0]["hops"],
            duration_ms=timer.duration_ms,
        )

    async def weighted_shortest_path(
        self, source_id: str, target_id: str, max_hops: int = 6
    ) -> TraversalResult:
        """Find path with minimum total weight (inverse of strength = cost)."""
        with PerformanceTimer("weighted_shortest_path") as timer:
            query = """
                MATCH (a {node_id: $source_id}), (b {node_id: $target_id})
                MATCH path = (a)-[*1..%d]-(b)
                WITH path,
                     reduce(cost = 0.0, r IN relationships(path) |
                         cost + (1.0 / coalesce(r.relationship_strength, 0.5))
                     ) AS total_cost
                ORDER BY total_cost ASC
                LIMIT 1
                RETURN
                    [n IN nodes(path) | {
                        node_id: n.node_id,
                        label: labels(n)[0],
                        properties: n {.*}
                    }] AS path_nodes,
                    [r IN relationships(path) | {
                        type: type(r),
                        weight: coalesce(r.relationship_strength, 1.0)
                    }] AS path_edges,
                    length(path) AS hops,
                    total_cost
            """ % max_hops
            records = await self._conn.execute_query(
                query, {"source_id": source_id, "target_id": target_id}
            )

        if not records:
            return TraversalResult(
                source_id=source_id,
                traversal_type="weighted_shortest_path",
                duration_ms=timer.duration_ms,
            )

        path_nodes_raw = records[0]["path_nodes"]
        path_edges_raw = records[0]["path_edges"]

        path_nodes = []
        for i, node_data in enumerate(path_nodes_raw):
            edge_type = path_edges_raw[i]["type"] if i < len(path_edges_raw) else ""
            edge_weight = path_edges_raw[i]["weight"] if i < len(path_edges_raw) else 1.0
            path_nodes.append(TraversalNode(
                node_id=node_data["node_id"],
                label=node_data["label"],
                properties=node_data["properties"],
                depth=i,
                parent_id=path_nodes_raw[i - 1]["node_id"] if i > 0 else None,
                edge_type=edge_type,
                edge_weight=edge_weight,
            ))

        return TraversalResult(
            source_id=source_id,
            traversal_type="weighted_shortest_path",
            visited_nodes=path_nodes,
            paths=[path_nodes],
            total_visited=len(path_nodes),
            max_depth_reached=records[0]["hops"],
            duration_ms=timer.duration_ms,
        )

    async def k_hop(
        self, source_id: str, k: int = 2, direction: str = "both"
    ) -> TraversalResult:
        """Retrieve all nodes exactly k hops away."""
        k = min(k, MAX_TRAVERSAL_DEPTH)

        with PerformanceTimer(f"k_hop(k={k})") as timer:
            if direction == "outgoing":
                pattern = f"(source)-[*{k}]->(neighbor)"
            elif direction == "incoming":
                pattern = f"(neighbor)-[*{k}]->(source)"
            else:
                pattern = f"(source)-[*{k}]-(neighbor)"

            query = f"""
                MATCH (source {{node_id: $source_id}})
                MATCH {pattern}
                WHERE neighbor <> source
                RETURN DISTINCT
                    neighbor.node_id AS node_id,
                    labels(neighbor)[0] AS label,
                    neighbor {{.*}} AS properties
                LIMIT 100
            """
            records = await self._conn.execute_query(query, {"source_id": source_id})

        visited = [
            TraversalNode(
                node_id=r["node_id"],
                label=r["label"],
                properties=r["properties"],
                depth=k,
            )
            for r in records
        ]

        return TraversalResult(
            source_id=source_id,
            traversal_type=f"k_hop_{k}",
            visited_nodes=visited,
            total_visited=len(visited),
            max_depth_reached=k,
            duration_ms=timer.duration_ms,
        )

    async def multi_hop_directed(
        self, source_id: str, max_depth: int = 3, direction: str = "upstream"
    ) -> TraversalResult:
        """Multi-hop directed traversal (upstream = incoming, downstream = outgoing)."""
        max_depth = min(max_depth, MAX_TRAVERSAL_DEPTH)

        with PerformanceTimer(f"multi_hop_{direction}") as timer:
            if direction == "upstream":
                pattern = f"(ancestor)-[*1..{max_depth}]->(source)"
                query = f"""
                    MATCH (source {{node_id: $source_id}})
                    MATCH path = {pattern}
                    WHERE ancestor <> source
                    WITH ancestor, length(path) AS depth, relationships(path) AS rels
                    RETURN DISTINCT
                        ancestor.node_id AS node_id,
                        labels(ancestor)[0] AS label,
                        ancestor {{.*}} AS properties,
                        min(depth) AS depth,
                        type(rels[0]) AS edge_type,
                        coalesce(rels[0].relationship_strength, 1.0) AS edge_weight
                    ORDER BY depth ASC
                    LIMIT 80
                """
            else:
                pattern = f"(source)-[*1..{max_depth}]->(descendant)"
                query = f"""
                    MATCH (source {{node_id: $source_id}})
                    MATCH path = {pattern}
                    WHERE descendant <> source
                    WITH descendant, length(path) AS depth, relationships(path) AS rels
                    RETURN DISTINCT
                        descendant.node_id AS node_id,
                        labels(descendant)[0] AS label,
                        descendant {{.*}} AS properties,
                        min(depth) AS depth,
                        type(rels[size(rels)-1]) AS edge_type,
                        coalesce(rels[size(rels)-1].relationship_strength, 1.0) AS edge_weight
                    ORDER BY depth ASC
                    LIMIT 80
                """
            records = await self._conn.execute_query(query, {"source_id": source_id})

        visited = [
            TraversalNode(
                node_id=r["node_id"],
                label=r["label"],
                properties=r["properties"],
                depth=r["depth"],
                edge_type=r["edge_type"],
                edge_weight=r["edge_weight"],
            )
            for r in records
        ]

        max_d = max((n.depth for n in visited), default=0)

        return TraversalResult(
            source_id=source_id,
            traversal_type=f"multi_hop_{direction}",
            visited_nodes=visited,
            total_visited=len(visited),
            max_depth_reached=max_d,
            duration_ms=timer.duration_ms,
        )

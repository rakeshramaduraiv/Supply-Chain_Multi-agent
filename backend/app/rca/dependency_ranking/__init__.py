"""
AMASCI RCA Dependency Ranking
================================
Critical node identification, bottleneck detection, supply chain impact ranking.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.rca.utils import PerformanceTimer, compute_risk_label, extract_node_risk

logger = logging.getLogger(__name__)


@dataclass
class RankedDependency:
    """A ranked dependency node."""
    node_id: str
    label: str
    rank: int = 0
    dependency_score: float = 0.0
    is_bottleneck: bool = False
    is_critical: bool = False
    downstream_count: int = 0
    upstream_count: int = 0
    risk_score: float = 0.0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "rank": self.rank,
            "dependency_score": round(self.dependency_score, 4),
            "is_bottleneck": self.is_bottleneck,
            "is_critical": self.is_critical,
            "downstream_count": self.downstream_count,
            "upstream_count": self.upstream_count,
            "risk_score": round(self.risk_score, 4),
        }


@dataclass
class DependencyRankingResult:
    """Result of dependency ranking analysis."""
    target_id: str
    ranked_dependencies: list[RankedDependency] = field(default_factory=list)
    bottlenecks: list[RankedDependency] = field(default_factory=list)
    critical_nodes: list[RankedDependency] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "ranked_dependencies": [d.to_dict() for d in self.ranked_dependencies],
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "critical_nodes": [c.to_dict() for c in self.critical_nodes],
            "total_dependencies": len(self.ranked_dependencies),
            "bottleneck_count": len(self.bottlenecks),
            "critical_count": len(self.critical_nodes),
            "duration_ms": round(self.duration_ms, 2),
        }


class DependencyRankingEngine:
    """
    Ranks dependencies by criticality for RCA.

    Provides:
    - Parent dependency detection
    - Child dependency detection
    - Critical path detection
    - Bottleneck detection
    - Supply chain impact propagation ranking
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def rank_dependencies(
        self, target_id: str, target_label: str, max_depth: int = 3, top_n: int = 15
    ) -> DependencyRankingResult:
        """Rank all dependencies of a target node by criticality."""
        with PerformanceTimer("rank_dependencies") as timer:
            # Get upstream (parent) dependencies
            parents = await self._get_parent_dependencies(target_id, target_label, max_depth)

            # Get downstream (child) dependencies
            children = await self._get_child_dependencies(target_id, target_label, max_depth)

            # Score and rank all dependencies
            all_deps = parents + children
            ranked = await self._score_dependencies(all_deps, target_id)

            # Sort by score
            ranked.sort(key=lambda d: d.dependency_score, reverse=True)
            for i, dep in enumerate(ranked):
                dep.rank = i + 1

            # Identify bottlenecks and critical nodes
            bottlenecks = [d for d in ranked if d.is_bottleneck]
            critical = [d for d in ranked if d.is_critical]

        return DependencyRankingResult(
            target_id=target_id,
            ranked_dependencies=ranked[:top_n],
            bottlenecks=bottlenecks[:5],
            critical_nodes=critical[:5],
            duration_ms=timer.duration_ms,
        )

    async def detect_bottlenecks(
        self, target_id: str, target_label: str
    ) -> list[RankedDependency]:
        """Detect bottleneck nodes (high betweenness, few alternatives)."""
        query = f"""
            MATCH (target:{target_label} {{node_id: $target_id}})-[*1..3]-(dep)
            WHERE dep <> target
            WITH dep
            MATCH (dep)-[r]-()
            WITH dep, count(r) AS degree
            WHERE degree >= 3
            OPTIONAL MATCH (dep)-[r2]-(other)
            WITH dep, degree,
                 count(DISTINCT other) AS connections
            OPTIONAL MATCH (alt)-[]->(dep)
            WITH dep, degree, connections,
                 count(DISTINCT alt) AS incoming
            WHERE incoming <= 1 AND connections >= 3
            RETURN
                dep.node_id AS node_id,
                labels(dep)[0] AS label,
                dep {{.*}} AS properties,
                degree,
                connections,
                incoming
            ORDER BY degree DESC
            LIMIT 10
        """
        records = await self._conn.execute_query(query, {"target_id": target_id})

        bottlenecks = []
        for r in records:
            props = r["properties"]
            bottlenecks.append(RankedDependency(
                node_id=r["node_id"],
                label=r["label"],
                is_bottleneck=True,
                downstream_count=r["connections"],
                upstream_count=r["incoming"],
                risk_score=extract_node_risk(props),
                properties=props,
            ))
        return bottlenecks

    async def detect_critical_path(
        self, source_id: str, target_id: str
    ) -> list[dict[str, Any]]:
        """Detect the critical path (highest risk path) between two nodes."""
        query = """
            MATCH (a {node_id: $source_id}), (b {node_id: $target_id})
            MATCH path = (a)-[*1..5]-(b)
            WITH path,
                 reduce(risk = 0.0, n IN nodes(path) |
                     risk + coalesce(n.risk_score, n.late_delivery_rate, n.warehouse_risk, 0.0)
                 ) AS path_risk,
                 length(path) AS hops
            ORDER BY path_risk DESC
            LIMIT 1
            RETURN
                [n IN nodes(path) | {
                    node_id: n.node_id,
                    label: labels(n)[0],
                    risk: coalesce(n.risk_score, n.late_delivery_rate, n.warehouse_risk, 0.0)
                }] AS critical_path,
                path_risk,
                hops
        """
        records = await self._conn.execute_query(
            query, {"source_id": source_id, "target_id": target_id}
        )
        if not records:
            return []
        return records[0]["critical_path"]

    async def _get_parent_dependencies(
        self, target_id: str, target_label: str, max_depth: int
    ) -> list[dict[str, Any]]:
        """Get upstream parent dependencies."""
        query = f"""
            MATCH (target:{target_label} {{node_id: $target_id}})
            MATCH path = (parent)-[*1..{max_depth}]->(target)
            WHERE parent <> target
            WITH parent, min(length(path)) AS distance
            RETURN
                parent.node_id AS node_id,
                labels(parent)[0] AS label,
                parent {{.*}} AS properties,
                distance,
                'parent' AS direction
            ORDER BY distance ASC
            LIMIT 30
        """
        records = await self._conn.execute_query(query, {"target_id": target_id})
        return records

    async def _get_child_dependencies(
        self, target_id: str, target_label: str, max_depth: int
    ) -> list[dict[str, Any]]:
        """Get downstream child dependencies."""
        query = f"""
            MATCH (target:{target_label} {{node_id: $target_id}})
            MATCH path = (target)-[*1..{max_depth}]->(child)
            WHERE child <> target
            WITH child, min(length(path)) AS distance
            RETURN
                child.node_id AS node_id,
                labels(child)[0] AS label,
                child {{.*}} AS properties,
                distance,
                'child' AS direction
            ORDER BY distance ASC
            LIMIT 30
        """
        records = await self._conn.execute_query(query, {"target_id": target_id})
        return records

    async def _score_dependencies(
        self, dependencies: list[dict[str, Any]], target_id: str
    ) -> list[RankedDependency]:
        """Score each dependency based on risk, connectivity, and position."""
        ranked: list[RankedDependency] = []

        for dep in dependencies:
            node_id = dep.get("node_id", "")
            label = dep.get("label", "Unknown")
            properties = dep.get("properties", {})
            distance = dep.get("distance", 1)
            direction = dep.get("direction", "parent")

            risk = extract_node_risk(properties)

            # Get connectivity
            connectivity = await self._get_connectivity(node_id, label)

            # Distance decay: closer = more critical
            distance_factor = 1.0 / (1.0 + distance * 0.3)

            # Direction weight: upstream more critical for RCA
            direction_weight = 1.2 if direction == "parent" else 0.8

            # Composite score
            score = (risk * 0.4 + connectivity * 0.3 + distance_factor * 0.3) * direction_weight

            is_bottleneck = connectivity > 0.6 and risk > 0.3
            is_critical = risk > 0.5 and distance <= 2

            ranked.append(RankedDependency(
                node_id=node_id,
                label=label,
                dependency_score=score,
                is_bottleneck=is_bottleneck,
                is_critical=is_critical,
                downstream_count=int(connectivity * 10),
                upstream_count=distance,
                risk_score=risk,
                properties=properties,
            ))

        return ranked

    async def _get_connectivity(self, node_id: str, label: str) -> float:
        """Get normalized connectivity score for a node."""
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})-[r]-()
            RETURN count(r) AS degree
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        degree = records[0]["degree"] if records else 0
        # Normalize: sigmoid-like scaling
        return min(1.0, degree / 15.0)

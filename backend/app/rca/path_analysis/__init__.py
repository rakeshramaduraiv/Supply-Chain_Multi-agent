"""
AMASCI RCA Path Analysis
===========================
Critical path detection, bottleneck identification, investigation path recommendation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.rca.graph_traversal import GraphTraversalEngine, TraversalResult
from app.rca.utils import PerformanceTimer, compute_risk_label, extract_node_risk

logger = logging.getLogger(__name__)


@dataclass
class PathNode:
    """A node in an analysis path."""
    node_id: str
    label: str
    risk_score: float = 0.0
    risk_level: str = "low"
    position: int = 0
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level,
            "position": self.position,
        }


@dataclass
class AnalysisPath:
    """A complete analysis path with risk scoring."""
    path_id: str
    path_type: str
    nodes: list[PathNode] = field(default_factory=list)
    total_risk: float = 0.0
    avg_risk: float = 0.0
    max_risk: float = 0.0
    length: int = 0
    bottleneck_node: PathNode | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "path_type": self.path_type,
            "nodes": [n.to_dict() for n in self.nodes],
            "total_risk": round(self.total_risk, 4),
            "avg_risk": round(self.avg_risk, 4),
            "max_risk": round(self.max_risk, 4),
            "length": self.length,
            "bottleneck_node": self.bottleneck_node.to_dict() if self.bottleneck_node else None,
        }


@dataclass
class PathAnalysisResult:
    """Complete path analysis result."""
    target_id: str
    investigation_paths: list[AnalysisPath] = field(default_factory=list)
    critical_path: AnalysisPath | None = None
    recommended_path: AnalysisPath | None = None
    bottleneck_nodes: list[PathNode] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "investigation_paths": [p.to_dict() for p in self.investigation_paths],
            "critical_path": self.critical_path.to_dict() if self.critical_path else None,
            "recommended_path": self.recommended_path.to_dict() if self.recommended_path else None,
            "bottleneck_nodes": [b.to_dict() for b in self.bottleneck_nodes],
            "total_paths": len(self.investigation_paths),
            "duration_ms": round(self.duration_ms, 2),
        }


class PathAnalysisEngine:
    """
    Path analysis engine for RCA investigation.

    Provides:
    - Critical path detection (highest cumulative risk)
    - Investigation path recommendation
    - Bottleneck identification along paths
    - Multi-path comparison
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()
        self._traversal = GraphTraversalEngine(self._conn)

    async def analyze_paths(
        self, target_id: str, target_label: str, max_paths: int = 5
    ) -> PathAnalysisResult:
        """Full path analysis for RCA investigation."""
        with PerformanceTimer("analyze_paths") as timer:
            # Find high-risk upstream paths
            investigation_paths = await self._find_investigation_paths(
                target_id, target_label, max_paths
            )

            # Identify critical path (highest total risk)
            critical_path = None
            if investigation_paths:
                critical_path = max(investigation_paths, key=lambda p: p.total_risk)

            # Recommend investigation path (highest avg risk, shortest)
            recommended_path = self._recommend_path(investigation_paths)

            # Collect all bottleneck nodes
            bottleneck_nodes = []
            for path in investigation_paths:
                if path.bottleneck_node:
                    bottleneck_nodes.append(path.bottleneck_node)

        return PathAnalysisResult(
            target_id=target_id,
            investigation_paths=investigation_paths,
            critical_path=critical_path,
            recommended_path=recommended_path,
            bottleneck_nodes=bottleneck_nodes,
            duration_ms=timer.duration_ms,
        )

    async def find_path_between(
        self, source_id: str, target_id: str
    ) -> AnalysisPath | None:
        """Find and analyze path between two specific nodes."""
        traversal = await self._traversal.shortest_path(source_id, target_id)
        if not traversal.visited_nodes:
            return None

        path_nodes = []
        for i, tnode in enumerate(traversal.visited_nodes):
            risk = extract_node_risk(tnode.properties)
            path_nodes.append(PathNode(
                node_id=tnode.node_id,
                label=tnode.label,
                risk_score=risk,
                risk_level=compute_risk_label(risk),
                position=i,
                properties=tnode.properties,
            ))

        return self._build_analysis_path(
            f"path_{source_id[:8]}_{target_id[:8]}",
            "shortest",
            path_nodes,
        )

    async def _find_investigation_paths(
        self, target_id: str, target_label: str, max_paths: int
    ) -> list[AnalysisPath]:
        """Find multiple investigation paths leading to the disrupted entity."""
        query = f"""
            MATCH (target:{target_label} {{node_id: $target_id}})
            MATCH path = (source)-[*1..4]->(target)
            WHERE source <> target
              AND (coalesce(source.risk_score, source.late_delivery_rate,
                   source.warehouse_risk, source.supplier_delay_rate, 0) > 0.2)
            WITH path, source,
                 reduce(risk = 0.0, n IN nodes(path) |
                     risk + coalesce(n.risk_score, n.late_delivery_rate,
                                     n.warehouse_risk, n.supplier_delay_rate, 0.0)
                 ) AS path_risk
            ORDER BY path_risk DESC
            LIMIT $max_paths
            RETURN
                [n IN nodes(path) | {{
                    node_id: n.node_id,
                    label: labels(n)[0],
                    properties: n {{.*}}
                }}] AS path_nodes,
                path_risk,
                length(path) AS hops
        """
        records = await self._conn.execute_query(
            query, {"target_id": target_id, "max_paths": max_paths}
        )

        paths = []
        for i, record in enumerate(records):
            path_nodes = []
            for j, node_data in enumerate(record["path_nodes"]):
                props = node_data.get("properties", {})
                risk = extract_node_risk(props)
                path_nodes.append(PathNode(
                    node_id=node_data["node_id"],
                    label=node_data["label"],
                    risk_score=risk,
                    risk_level=compute_risk_label(risk),
                    position=j,
                    properties=props,
                ))

            analysis_path = self._build_analysis_path(
                f"inv_path_{i}", "investigation", path_nodes
            )
            paths.append(analysis_path)

        return paths

    def _build_analysis_path(
        self, path_id: str, path_type: str, nodes: list[PathNode]
    ) -> AnalysisPath:
        """Build an AnalysisPath with computed metrics."""
        risks = [n.risk_score for n in nodes]
        total_risk = sum(risks)
        avg_risk = total_risk / len(risks) if risks else 0.0
        max_risk = max(risks) if risks else 0.0

        # Bottleneck = node with highest risk in the path
        bottleneck = max(nodes, key=lambda n: n.risk_score) if nodes else None

        return AnalysisPath(
            path_id=path_id,
            path_type=path_type,
            nodes=nodes,
            total_risk=total_risk,
            avg_risk=avg_risk,
            max_risk=max_risk,
            length=len(nodes),
            bottleneck_node=bottleneck,
        )

    def _recommend_path(self, paths: list[AnalysisPath]) -> AnalysisPath | None:
        """Recommend the best investigation path (high avg risk, reasonable length)."""
        if not paths:
            return None
        # Score: avg_risk * (1 / length) to prefer shorter high-risk paths
        scored = [
            (p, p.avg_risk * (1.0 / max(p.length, 1)))
            for p in paths
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

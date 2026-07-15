"""
AMASCI GraphRAG Dependency Analysis
======================================
Ancestor/descendant analysis, critical dependency detection, impact propagation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager
from app.graphrag.utils import PerformanceTimer, compute_risk_label

logger = logging.getLogger(__name__)

RISK_PROPAGATION_DECAY = 0.7


@dataclass
class DependencyResult:
    """Result of a dependency analysis."""
    entity_id: str
    entity_label: str
    ancestors: list[dict[str, Any]] = field(default_factory=list)
    descendants: list[dict[str, Any]] = field(default_factory=list)
    critical_dependencies: list[dict[str, Any]] = field(default_factory=list)
    impact_score: float = 0.0
    dependency_depth: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_label": self.entity_label,
            "ancestors": self.ancestors,
            "descendants": self.descendants,
            "critical_dependencies": self.critical_dependencies,
            "impact_score": round(self.impact_score, 4),
            "dependency_depth": self.dependency_depth,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class ImpactPropagation:
    """Result of impact propagation analysis."""
    source_id: str
    source_label: str
    impacted_nodes: list[dict[str, Any]] = field(default_factory=list)
    total_impact: float = 0.0
    propagation_depth: int = 0
    risk_amplification: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_label": self.source_label,
            "impacted_nodes": self.impacted_nodes,
            "total_impact": round(self.total_impact, 4),
            "propagation_depth": self.propagation_depth,
            "risk_amplification": round(self.risk_amplification, 4),
        }


class DependencyAnalyzer:
    """
    Supply chain dependency analysis engine.

    Provides:
    - Ancestor analysis (upstream dependencies)
    - Descendant analysis (downstream dependents)
    - Critical dependency detection
    - Supply chain dependency mapping
    - Impact propagation simulation
    - Relationship ranking by importance
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def analyze_dependencies(
        self, node_id: str, label: str, max_depth: int = 3
    ) -> DependencyResult:
        """Full dependency analysis for an entity."""
        with PerformanceTimer("analyze_dependencies") as timer:
            ancestors = await self.get_ancestors(node_id, label, max_depth)
            descendants = await self.get_descendants(node_id, label, max_depth)
            critical = await self.detect_critical_dependencies(node_id, label)
            impact = self._compute_impact_score(ancestors, descendants)
            depth = max(len(ancestors), len(descendants))

        return DependencyResult(
            entity_id=node_id,
            entity_label=label,
            ancestors=ancestors,
            descendants=descendants,
            critical_dependencies=critical,
            impact_score=impact,
            dependency_depth=depth,
            duration_ms=timer.duration_ms,
        )

    async def get_ancestors(
        self, node_id: str, label: str, max_depth: int = 3
    ) -> list[dict[str, Any]]:
        """Get upstream dependencies (nodes that feed into this entity)."""
        query = f"""
            MATCH (target:{label} {{node_id: $node_id}})
            MATCH path = (ancestor)-[*1..{max_depth}]->(target)
            WHERE ancestor <> target
            WITH ancestor, length(path) AS distance, relationships(path) AS rels
            RETURN DISTINCT
                ancestor.node_id AS node_id,
                labels(ancestor)[0] AS label,
                ancestor {{.*}} AS properties,
                min(distance) AS min_distance,
                type(rels[0]) AS relationship_type
            ORDER BY min_distance ASC
            LIMIT 50
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        return [
            {
                "node_id": r["node_id"],
                "label": r["label"],
                "properties": r["properties"],
                "distance": r["min_distance"],
                "relationship_type": r["relationship_type"],
            }
            for r in records
        ]

    async def get_descendants(
        self, node_id: str, label: str, max_depth: int = 3
    ) -> list[dict[str, Any]]:
        """Get downstream dependents (nodes that depend on this entity)."""
        query = f"""
            MATCH (source:{label} {{node_id: $node_id}})
            MATCH path = (source)-[*1..{max_depth}]->(descendant)
            WHERE descendant <> source
            WITH descendant, length(path) AS distance, relationships(path) AS rels
            RETURN DISTINCT
                descendant.node_id AS node_id,
                labels(descendant)[0] AS label,
                descendant {{.*}} AS properties,
                min(distance) AS min_distance,
                type(rels[0]) AS relationship_type
            ORDER BY min_distance ASC
            LIMIT 50
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        return [
            {
                "node_id": r["node_id"],
                "label": r["label"],
                "properties": r["properties"],
                "distance": r["min_distance"],
                "relationship_type": r["relationship_type"],
            }
            for r in records
        ]

    async def detect_critical_dependencies(
        self, node_id: str, label: str
    ) -> list[dict[str, Any]]:
        """
        Detect critical dependencies: nodes that are single points of failure.
        A dependency is critical if removing it disconnects the entity from key resources.
        """
        query = f"""
            MATCH (target:{label} {{node_id: $node_id}})-[r]-(neighbor)
            WITH neighbor, type(r) AS rel_type, r,
                 coalesce(r.relationship_strength, 1.0) AS strength
            OPTIONAL MATCH (neighbor)-[r2]-(other)
            WHERE other.node_id <> $node_id
            WITH neighbor, rel_type, strength,
                 count(DISTINCT other) AS alternative_connections
            WHERE alternative_connections <= 2
            RETURN
                neighbor.node_id AS node_id,
                labels(neighbor)[0] AS label,
                neighbor {{.*}} AS properties,
                rel_type AS relationship_type,
                strength,
                alternative_connections,
                CASE WHEN alternative_connections = 0 THEN 'sole_dependency'
                     WHEN alternative_connections = 1 THEN 'near_sole_dependency'
                     ELSE 'limited_alternatives'
                END AS criticality
            ORDER BY alternative_connections ASC, strength DESC
            LIMIT 20
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        return [
            {
                "node_id": r["node_id"],
                "label": r["label"],
                "properties": r["properties"],
                "relationship_type": r["relationship_type"],
                "strength": r["strength"],
                "alternative_connections": r["alternative_connections"],
                "criticality": r["criticality"],
            }
            for r in records
        ]

    async def map_supply_chain(self, node_id: str, label: str) -> dict[str, Any]:
        """Map the full supply chain path for an entity."""
        query = f"""
            MATCH (entity:{label} {{node_id: $node_id}})
            OPTIONAL MATCH upstream = (supplier:Supplier)-[*]->(entity)
            OPTIONAL MATCH downstream = (entity)-[*]->(customer:Customer)
            WITH entity,
                 collect(DISTINCT supplier {{.*, _label: 'Supplier'}}) AS suppliers,
                 collect(DISTINCT customer {{.*, _label: 'Customer'}}) AS customers
            OPTIONAL MATCH (entity)-[:STORED_IN|SHIPS_VIA*1..2]-(logistics)
            WHERE labels(logistics)[0] IN ['Warehouse', 'Shipment']
            RETURN
                entity {{.*}} AS entity,
                suppliers[0..10] AS upstream_suppliers,
                customers[0..10] AS downstream_customers,
                collect(DISTINCT logistics {{.*, _label: labels(logistics)[0]}}) AS logistics_nodes
        """
        records = await self._conn.execute_query(query, {"node_id": node_id})
        if not records:
            return {"entity": None, "upstream": [], "downstream": [], "logistics": []}

        return {
            "entity": records[0]["entity"],
            "upstream_suppliers": records[0]["upstream_suppliers"],
            "downstream_customers": records[0]["downstream_customers"],
            "logistics_nodes": records[0]["logistics_nodes"],
        }

    async def propagate_impact(
        self, source_id: str, source_label: str, initial_risk: float = 1.0, max_depth: int = 3
    ) -> ImpactPropagation:
        """Simulate risk impact propagation from a source node."""
        with PerformanceTimer("propagate_impact"):
            impacted: list[dict[str, Any]] = []
            total_impact = 0.0

            for depth in range(1, max_depth + 1):
                decay_factor = RISK_PROPAGATION_DECAY ** depth
                propagated_risk = initial_risk * decay_factor

                query = f"""
                    MATCH (source:{source_label} {{node_id: $source_id}})
                    MATCH path = (source)-[*{depth}]-(target)
                    WHERE target <> source
                    WITH DISTINCT target, $propagated_risk AS risk_contribution
                    RETURN
                        target.node_id AS node_id,
                        labels(target)[0] AS label,
                        target {{.*}} AS properties,
                        risk_contribution,
                        {depth} AS depth
                    LIMIT 30
                """
                records = await self._conn.execute_query(
                    query,
                    {"source_id": source_id, "propagated_risk": propagated_risk},
                )

                for r in records:
                    existing_ids = {n["node_id"] for n in impacted}
                    if r["node_id"] not in existing_ids:
                        impacted.append({
                            "node_id": r["node_id"],
                            "label": r["label"],
                            "properties": r["properties"],
                            "risk_contribution": round(r["risk_contribution"], 4),
                            "depth": r["depth"],
                            "risk_level": compute_risk_label(r["risk_contribution"]),
                        })
                        total_impact += r["risk_contribution"]

        return ImpactPropagation(
            source_id=source_id,
            source_label=source_label,
            impacted_nodes=impacted,
            total_impact=total_impact,
            propagation_depth=max_depth,
            risk_amplification=total_impact / initial_risk if initial_risk > 0 else 1.0,
        )

    async def rank_relationships(
        self, node_id: str, label: str, top_n: int = 10
    ) -> list[dict[str, Any]]:
        """Rank relationships by importance (strength, centrality contribution)."""
        query = f"""
            MATCH (n:{label} {{node_id: $node_id}})-[r]-(m)
            WITH m, r, type(r) AS rel_type,
                 coalesce(r.relationship_strength, 1.0) AS strength
            OPTIONAL MATCH (m)-[r2]-()
            WITH m, rel_type, strength, count(r2) AS neighbor_degree
            RETURN
                m.node_id AS node_id,
                labels(m)[0] AS label,
                rel_type,
                strength,
                neighbor_degree,
                strength * log(toFloat(neighbor_degree) + 1) AS importance_score
            ORDER BY importance_score DESC
            LIMIT $top_n
        """
        records = await self._conn.execute_query(query, {"node_id": node_id, "top_n": top_n})
        return [
            {
                "node_id": r["node_id"],
                "label": r["label"],
                "relationship_type": r["rel_type"],
                "strength": round(r["strength"], 4),
                "neighbor_degree": r["neighbor_degree"],
                "importance_score": round(r["importance_score"], 4),
            }
            for r in records
        ]

    def _compute_impact_score(
        self, ancestors: list[dict[str, Any]], descendants: list[dict[str, Any]]
    ) -> float:
        """Compute overall impact score based on dependency structure."""
        upstream_weight = len(ancestors) * 0.3
        downstream_weight = len(descendants) * 0.7
        total = upstream_weight + downstream_weight
        return min(1.0, total / 20.0)

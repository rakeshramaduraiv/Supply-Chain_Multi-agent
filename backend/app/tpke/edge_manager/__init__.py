"""
TPKE Edge Manager
==================
Manages Neo4j TPKE-inferred edge lifecycle: create, strengthen, decay, remove.
Persists all mutations to PostgreSQL tpke_logs table.

Edge Decay Formula:
    w_new = w_old × (1 - decay_rate) ^ days_since_last_update

    Example:
        decay_rate = 0.05 (5% per day)
        w_old = 0.95, days_elapsed = 30
        w_new = 0.95 × (0.95)^30 = 0.95 × 0.215 = 0.204

    If w_new < TPKE_MIN_EDGE_WEIGHT (0.1) → edge removed

Edge Strengthening Formula:
    When a pattern is observed again on an existing edge:
        w_new = min(w_old × 0.6 + new_weight × 0.4, 1.0)

    This means:
        - Old evidence retains 60% weight
        - New evidence contributes 40%
        - Edge can never exceed 1.0

TPKE edges in Neo4j:
    (SupplierA)-[:TPKE_INFERRED {
        relationship_type: "LATE_DELIVERY_TRIGGERS_STOCKOUT",
        weight: 0.85,
        confidence: 0.85,
        frequency: 80,
        ...
    }]->(ProductB)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import TPKE_MIN_EDGE_WEIGHT, TPKE_MAX_EDGE_WEIGHT
from app.graph.connection import Neo4jConnectionManager
from app.services.domain.tpke_service import TPKELogService
from app.tpke.pattern import TemporalPattern

logger = logging.getLogger(__name__)


@dataclass
class EdgeMutation:
    """Record of a single edge mutation."""
    action: str          # edge_created | edge_strengthened | edge_decayed | edge_removed
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relationship_type: str
    weight_before: float | None
    weight_after: float | None
    frequency: int = 1


@dataclass
class DecayResult:
    """Summary of edge decay pass."""
    edges_decayed: int = 0
    edges_removed: int = 0
    mutations: list[EdgeMutation] = field(default_factory=list)


# ─── Cypher Queries ───────────────────────────────────────────────────────────

# Find an existing TPKE edge by source, target, and causal relationship type
_FIND_TPKE_EDGE = """
    MATCH (s {entity_id: $source_id})-[r:TPKE_INFERRED]->(t {entity_id: $target_id})
    WHERE r.relationship_type = $rel_type
    RETURN r.weight AS weight, r.frequency AS frequency,
           r.last_updated AS last_updated, r.created_at AS created_at
"""

# Create a new TPKE-inferred edge
# relationship_type stores the causal label (e.g. LATE_DELIVERY_TRIGGERS_STOCKOUT)
_CREATE_TPKE_EDGE = """
    MATCH (s {entity_id: $source_id}), (t {entity_id: $target_id})
    CREATE (s)-[r:TPKE_INFERRED {
        relationship_type: $rel_type,
        weight:            $weight,
        confidence:        $confidence,
        frequency:         $frequency,
        temporal_score:    $temporal_score,
        source_type:       $source_type,
        target_type:       $target_type,
        created_at:        $now,
        last_updated:      $now
    }]->(t)
    RETURN r.weight AS weight
"""

# Strengthen or update an existing TPKE edge
_UPDATE_TPKE_EDGE = """
    MATCH (s {entity_id: $source_id})-[r:TPKE_INFERRED]->(t {entity_id: $target_id})
    WHERE r.relationship_type = $rel_type
    SET r.weight         = $weight,
        r.confidence     = $confidence,
        r.frequency      = $frequency,
        r.temporal_score = $temporal_score,
        r.last_updated   = $now
    RETURN r.weight AS weight
"""

# Remove a TPKE edge (weight fell below minimum threshold)
_REMOVE_TPKE_EDGE = """
    MATCH (s {entity_id: $source_id})-[r:TPKE_INFERRED]->(t {entity_id: $target_id})
    WHERE r.relationship_type = $rel_type
    DELETE r
    RETURN count(r) AS deleted
"""

# Retrieve all TPKE edges for decay pass
_GET_ALL_TPKE_EDGES = """
    MATCH (s)-[r:TPKE_INFERRED]->(t)
    RETURN s.entity_id      AS source_id,
           labels(s)[0]     AS source_type,
           t.entity_id      AS target_id,
           labels(t)[0]     AS target_type,
           r.relationship_type AS rel_type,
           r.weight         AS weight,
           r.frequency      AS frequency,
           r.last_updated   AS last_updated
"""

_COUNT_TPKE_EDGES = """
    MATCH ()-[r:TPKE_INFERRED]->()
    RETURN count(r) AS count
"""


class EdgeManager:
    """
    Manages TPKE-inferred edges in Neo4j.

    Operations:
    - evolve():  Apply detected patterns → create or strengthen edges
    - decay():   Time-based weight reduction on all TPKE edges
    """

    def __init__(self, connection: Neo4jConnectionManager, session: AsyncSession):
        self._conn = connection
        self._session = session
        self._tpke_service = TPKELogService(session)
        self._settings = get_settings()
        self._decay_rate = self._settings.tpke_decay_rate
        self._mutations: list[EdgeMutation] = []

    # ── Evolve ────────────────────────────────────────────────────────────────

    async def evolve(
        self,
        patterns: list[TemporalPattern],
        graph_version_id: str | None = None,
        triggered_by: str = "system",
    ) -> list[EdgeMutation]:
        """
        Apply temporal patterns to the graph.

        For each pattern:
        - If edge does NOT exist → create it with weight = pattern.weight
        - If edge DOES exist     → strengthen it:
              w_new = min(w_old × 0.6 + pattern.weight × 0.4, 1.0)
        """
        self._mutations = []
        now = datetime.now(timezone.utc).isoformat()

        for pattern in patterns:
            existing = await self._find_edge(pattern)
            if existing:
                await self._strengthen_edge(pattern, existing, now)
            else:
                await self._create_edge(pattern, now)

        # Persist all mutations to PostgreSQL
        for m in self._mutations:
            await self._tpke_service.log_mutation(
                action=m.action,
                source_node_id=m.source_id,
                source_node_type=m.source_type,
                target_node_id=m.target_id,
                target_node_type=m.target_type,
                relationship_type=m.relationship_type,
                confidence_before=m.weight_before,
                confidence_after=m.weight_after,
                frequency=m.frequency,
                evidence={"triggered_by": triggered_by},
                graph_version_id=graph_version_id,
                triggered_by=triggered_by,
            )

        logger.info(f"TPKE evolve: {len(self._mutations)} mutations applied")
        return self._mutations

    # ── Decay ─────────────────────────────────────────────────────────────────

    async def decay(self, reference_time: datetime | None = None) -> DecayResult:
        """
        Apply time-based decay to all TPKE-inferred edges.

        Formula:
            w_new = w_old × (1 - decay_rate) ^ days_since_last_update

        Example (decay_rate=0.05):
            Day 0:  w = 0.95
            Day 30: w = 0.95 × (0.95)^30 = 0.204
            Day 60: w = 0.95 × (0.95)^60 = 0.044 → removed

        If w_new < TPKE_MIN_EDGE_WEIGHT (0.1) → edge removed from graph.
        """
        ref = reference_time or datetime.now(timezone.utc)
        result = DecayResult()

        edges = await self._conn.execute_query(_GET_ALL_TPKE_EDGES)

        for edge in edges:
            last_updated_str = edge.get("last_updated")
            if not last_updated_str:
                continue

            try:
                last_updated = datetime.fromisoformat(last_updated_str)
                if last_updated.tzinfo is None:
                    last_updated = last_updated.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            days_elapsed = (ref - last_updated).total_seconds() / 86400.0
            if days_elapsed < 1.0:
                # Less than 1 day since last update — skip
                continue

            old_weight = float(edge.get("weight", 0.5))

            # w_new = w_old × (1 - decay_rate) ^ days_elapsed
            new_weight = old_weight * ((1.0 - self._decay_rate) ** days_elapsed)
            new_weight = round(new_weight, 4)

            source_id = edge["source_id"]
            target_id = edge["target_id"]
            rel_type = edge["rel_type"]

            if new_weight < TPKE_MIN_EDGE_WEIGHT:
                # Weight fell below minimum → remove edge
                await self._conn.execute_write(_REMOVE_TPKE_EDGE, {
                    "source_id": source_id,
                    "target_id": target_id,
                    "rel_type": rel_type,
                })
                mutation = EdgeMutation(
                    action="edge_removed",
                    source_id=source_id,
                    source_type=edge.get("source_type", "Unknown"),
                    target_id=target_id,
                    target_type=edge.get("target_type", "Unknown"),
                    relationship_type=rel_type,
                    weight_before=old_weight,
                    weight_after=0.0,
                    frequency=edge.get("frequency", 1),
                )
                result.edges_removed += 1
                result.mutations.append(mutation)

                logger.debug(
                    f"TPKE decay removed: {source_id} →[{rel_type}]→ {target_id} "
                    f"(w={old_weight} → {new_weight} < {TPKE_MIN_EDGE_WEIGHT})"
                )
            else:
                # Decay the edge weight
                await self._conn.execute_write(_UPDATE_TPKE_EDGE, {
                    "source_id": source_id,
                    "target_id": target_id,
                    "rel_type": rel_type,
                    "weight": new_weight,
                    "confidence": new_weight,
                    "frequency": edge.get("frequency", 1),
                    "temporal_score": new_weight,
                    "now": ref.isoformat(),
                })
                mutation = EdgeMutation(
                    action="edge_decayed",
                    source_id=source_id,
                    source_type=edge.get("source_type", "Unknown"),
                    target_id=target_id,
                    target_type=edge.get("target_type", "Unknown"),
                    relationship_type=rel_type,
                    weight_before=old_weight,
                    weight_after=new_weight,
                    frequency=edge.get("frequency", 1),
                )
                result.edges_decayed += 1
                result.mutations.append(mutation)

                logger.debug(
                    f"TPKE decay: {source_id} →[{rel_type}]→ {target_id} "
                    f"w={old_weight} → {new_weight} ({days_elapsed:.1f} days)"
                )

        # Persist decay mutations to PostgreSQL
        for m in result.mutations:
            await self._tpke_service.log_mutation(
                action=m.action,
                source_node_id=m.source_id,
                source_node_type=m.source_type,
                target_node_id=m.target_id,
                target_node_type=m.target_type,
                relationship_type=m.relationship_type,
                confidence_before=m.weight_before,
                confidence_after=m.weight_after,
                frequency=m.frequency,
                triggered_by="decay_engine",
            )

        logger.info(
            f"TPKE decay pass: {result.edges_decayed} decayed, "
            f"{result.edges_removed} removed"
        )
        return result

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_edge_count(self) -> int:
        """Get total count of TPKE-inferred edges."""
        records = await self._conn.execute_query(_COUNT_TPKE_EDGES)
        return records[0]["count"] if records else 0

    async def get_all_edges(self) -> list[dict[str, Any]]:
        """Get all TPKE-inferred edges."""
        return await self._conn.execute_query(_GET_ALL_TPKE_EDGES)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _find_edge(self, pattern: TemporalPattern) -> dict[str, Any] | None:
        """Check if a TPKE edge already exists for this pattern."""
        records = await self._conn.execute_query(_FIND_TPKE_EDGE, {
            "source_id": pattern.source_id,
            "target_id": pattern.target_id,
            "rel_type": pattern.relationship_type,
        })
        return records[0] if records else None

    async def _create_edge(self, pattern: TemporalPattern, now: str) -> None:
        """
        Create a new TPKE-inferred edge.

        The edge stores:
        - relationship_type: causal label (e.g. LATE_DELIVERY_TRIGGERS_STOCKOUT)
        - weight: pattern.weight (α·P(B|A) + β·freq_norm + γ·temporal)
        - confidence: P(B|A)
        - frequency: K occurrences observed
        """
        weight = min(pattern.weight, TPKE_MAX_EDGE_WEIGHT)

        await self._conn.execute_write(_CREATE_TPKE_EDGE, {
            "source_id":     pattern.source_id,
            "target_id":     pattern.target_id,
            "rel_type":      pattern.relationship_type,
            "weight":        weight,
            "confidence":    pattern.confidence,
            "frequency":     pattern.frequency,
            "temporal_score": pattern.temporal_score,
            "source_type":   pattern.source_type,
            "target_type":   pattern.target_type,
            "now":           now,
        })

        self._mutations.append(EdgeMutation(
            action="edge_created",
            source_id=pattern.source_id,
            source_type=pattern.source_type,
            target_id=pattern.target_id,
            target_type=pattern.target_type,
            relationship_type=pattern.relationship_type,
            weight_before=None,
            weight_after=weight,
            frequency=pattern.frequency,
        ))

        logger.info(
            f"TPKE created: {pattern.source_type}:{pattern.source_id} "
            f"→[{pattern.relationship_type}]→ "
            f"{pattern.target_type}:{pattern.target_id} "
            f"w={weight}, P(B|A)={pattern.confidence}, K={pattern.frequency}"
        )

    async def _strengthen_edge(
        self,
        pattern: TemporalPattern,
        existing: dict[str, Any],
        now: str,
    ) -> None:
        """
        Strengthen an existing TPKE edge with new evidence.

        Formula:
            w_new = min(w_old × 0.6 + new_weight × 0.4, 1.0)

        Old evidence retains 60%, new evidence contributes 40%.
        Frequency accumulates.
        """
        old_weight = float(existing.get("weight", 0.5))
        old_freq = int(existing.get("frequency", 1))

        new_weight = min(old_weight * 0.6 + pattern.weight * 0.4, TPKE_MAX_EDGE_WEIGHT)
        new_weight = round(new_weight, 4)
        new_freq = old_freq + pattern.frequency

        await self._conn.execute_write(_UPDATE_TPKE_EDGE, {
            "source_id":     pattern.source_id,
            "target_id":     pattern.target_id,
            "rel_type":      pattern.relationship_type,
            "weight":        new_weight,
            "confidence":    pattern.confidence,
            "frequency":     new_freq,
            "temporal_score": pattern.temporal_score,
            "now":           now,
        })

        self._mutations.append(EdgeMutation(
            action="edge_strengthened",
            source_id=pattern.source_id,
            source_type=pattern.source_type,
            target_id=pattern.target_id,
            target_type=pattern.target_type,
            relationship_type=pattern.relationship_type,
            weight_before=old_weight,
            weight_after=new_weight,
            frequency=new_freq,
        ))

        logger.info(
            f"TPKE strengthened: {pattern.source_type}:{pattern.source_id} "
            f"→[{pattern.relationship_type}]→ "
            f"{pattern.target_type}:{pattern.target_id} "
            f"w={old_weight} → {new_weight}, K={new_freq}"
        )

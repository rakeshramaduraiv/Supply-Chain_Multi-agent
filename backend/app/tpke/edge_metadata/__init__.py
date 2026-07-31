"""
AMASCI Enhanced TPKE Edge Metadata
=====================================
Enriches TPKE-inferred edges with full temporal and quality metadata.

Each TPKE edge stores:
  - created_date        ISO timestamp of first creation
  - last_updated        ISO timestamp of most recent update
  - occurrence_count    total number of times this pattern was observed (K)
  - confidence_score    P(B|A) conditional probability
  - importance_score    categorical: Low / Medium / High / Critical
  - decay_score         current weight after time-based decay

Example Neo4j edge properties:
    (Holiday)-[:TPKE_INFERRED {
        relationship_type:  "SEASONAL_STOCKOUT_RISK",
        weight:             0.92,
        confidence:         0.92,
        frequency:          31,
        created_date:       "2026-01-15T08:00:00+00:00",
        last_updated:       "2026-07-28T10:00:00+00:00",
        occurrence_count:   31,
        confidence_score:   0.92,
        importance_score:   "High",
        decay_score:        0.87,
    }]->(Warehouse)

Usage
-----
    from app.tpke.edge_metadata import EdgeMetadataEnricher

    enricher = EdgeMetadataEnricher(connection)
    await enricher.enrich_all()          # backfill existing edges
    await enricher.enrich_edge(...)      # enrich a single edge on creation
    summary = await enricher.get_summary()
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


def _importance_label(weight: float, frequency: int) -> str:
    """Derive importance label from weight and frequency."""
    score = weight * 0.6 + min(1.0, frequency / 50.0) * 0.4
    if score >= 0.75:
        return "Critical"
    elif score >= 0.50:
        return "High"
    elif score >= 0.25:
        return "Medium"
    return "Low"


# ── Cypher queries ────────────────────────────────────────────────────────────

_ENRICH_SINGLE = """
MATCH (s {entity_id: $source_id})-[r:TPKE_INFERRED]->(t {entity_id: $target_id})
WHERE r.relationship_type = $rel_type
SET r.occurrence_count  = coalesce(r.frequency, 1),
    r.confidence_score  = coalesce(r.confidence, r.weight, 0.5),
    r.importance_score  = $importance,
    r.decay_score       = coalesce(r.weight, 0.5),
    r.created_date      = coalesce(r.created_at, $now),
    r.last_updated      = $now
RETURN count(r) AS updated
"""

_ENRICH_ALL = """
MATCH (s)-[r:TPKE_INFERRED]->(t)
WHERE r.occurrence_count IS NULL
  OR  r.importance_score IS NULL
  OR  r.decay_score IS NULL
SET r.occurrence_count  = coalesce(r.frequency, 1),
    r.confidence_score  = coalesce(r.confidence, r.weight, 0.5),
    r.importance_score  = CASE
        WHEN coalesce(r.weight, 0) * 0.6 + toFloat(coalesce(r.frequency, 1)) / 50.0 * 0.4 >= 0.75 THEN 'Critical'
        WHEN coalesce(r.weight, 0) * 0.6 + toFloat(coalesce(r.frequency, 1)) / 50.0 * 0.4 >= 0.50 THEN 'High'
        WHEN coalesce(r.weight, 0) * 0.6 + toFloat(coalesce(r.frequency, 1)) / 50.0 * 0.4 >= 0.25 THEN 'Medium'
        ELSE 'Low'
    END,
    r.decay_score       = coalesce(r.weight, 0.5),
    r.created_date      = coalesce(r.created_at, $now),
    r.last_updated      = $now
RETURN count(r) AS updated
"""

_GET_ENRICHED_EDGES = """
MATCH (s)-[r:TPKE_INFERRED]->(t)
RETURN s.entity_id      AS source_id,
       labels(s)[0]     AS source_type,
       t.entity_id      AS target_id,
       labels(t)[0]     AS target_type,
       r.relationship_type  AS relationship_type,
       r.weight             AS weight,
       r.confidence_score   AS confidence_score,
       r.occurrence_count   AS occurrence_count,
       r.importance_score   AS importance_score,
       r.decay_score        AS decay_score,
       r.created_date       AS created_date,
       r.last_updated       AS last_updated
ORDER BY r.weight DESC
LIMIT $limit
"""

_SUMMARY_QUERY = """
MATCH ()-[r:TPKE_INFERRED]->()
RETURN count(r)                                          AS total_edges,
       avg(coalesce(r.weight, 0))                        AS avg_weight,
       avg(coalesce(r.confidence_score, 0))              AS avg_confidence,
       avg(toFloat(coalesce(r.occurrence_count, 1)))     AS avg_occurrences,
       sum(CASE WHEN r.importance_score = 'Critical' THEN 1 ELSE 0 END) AS critical_count,
       sum(CASE WHEN r.importance_score = 'High'     THEN 1 ELSE 0 END) AS high_count,
       sum(CASE WHEN r.importance_score = 'Medium'   THEN 1 ELSE 0 END) AS medium_count,
       sum(CASE WHEN r.importance_score = 'Low'      THEN 1 ELSE 0 END) AS low_count
"""


class EdgeMetadataEnricher:
    """
    Enriches TPKE-inferred edges with full temporal and quality metadata.

    Designed to be called:
      1. After EdgeManager.evolve() to enrich newly created/strengthened edges.
      2. As a one-time backfill via enrich_all() for existing edges.
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def enrich_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        weight: float,
        frequency: int,
    ) -> bool:
        """Enrich a single TPKE edge with metadata."""
        now = datetime.now(timezone.utc).isoformat()
        importance = _importance_label(weight, frequency)
        try:
            records = await self._conn.execute_write(_ENRICH_SINGLE, {
                "source_id": source_id,
                "target_id": target_id,
                "rel_type": rel_type,
                "importance": importance,
                "now": now,
            })
            updated = records[0]["updated"] if records else 0
            return updated > 0
        except Exception as e:
            logger.error(f"[EdgeMetadata] Failed to enrich edge {source_id}→{target_id}: {e}")
            return False

    async def enrich_all(self) -> int:
        """
        Backfill metadata on all TPKE edges that are missing enrichment fields.
        Returns the number of edges updated.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            records = await self._conn.execute_write(_ENRICH_ALL, {"now": now})
            updated = records[0]["updated"] if records else 0
            logger.info(f"[EdgeMetadata] Backfilled {updated} TPKE edges with metadata")
            return updated
        except Exception as e:
            logger.error(f"[EdgeMetadata] Backfill failed: {e}")
            return 0

    async def get_enriched_edges(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return enriched TPKE edges ordered by weight descending."""
        try:
            return await self._conn.execute_query(_GET_ENRICHED_EDGES, {"limit": limit})
        except Exception as e:
            logger.error(f"[EdgeMetadata] Failed to retrieve enriched edges: {e}")
            return []

    async def get_summary(self) -> dict[str, Any]:
        """Return aggregate statistics for all enriched TPKE edges."""
        try:
            records = await self._conn.execute_query(_SUMMARY_QUERY)
            if not records:
                return {"total_edges": 0}
            r = records[0]
            return {
                "total_edges": int(r.get("total_edges", 0)),
                "avg_weight": round(float(r.get("avg_weight") or 0), 4),
                "avg_confidence": round(float(r.get("avg_confidence") or 0), 4),
                "avg_occurrences": round(float(r.get("avg_occurrences") or 0), 2),
                "importance_distribution": {
                    "Critical": int(r.get("critical_count", 0)),
                    "High":     int(r.get("high_count", 0)),
                    "Medium":   int(r.get("medium_count", 0)),
                    "Low":      int(r.get("low_count", 0)),
                },
            }
        except Exception as e:
            logger.error(f"[EdgeMetadata] Summary query failed: {e}")
            return {"total_edges": 0, "error": str(e)}

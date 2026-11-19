"""
AMASCI RCA Integration Layer
============================
Writes Root Cause Analysis results (:CAUSES relationships and contribution scores)
into Neo4j post-analysis without rebuilding the graph.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


_CREATE_RCA_CAUSES_RELATIONSHIP = """
UNWIND $batch AS p
MATCH (cause) WHERE cause.node_id = p.cause_id OR cause.supplier_name = p.cause_id OR cause.category_name = p.cause_id
MATCH (target) WHERE target.node_id = p.target_id OR target.order_id = p.target_id
MERGE (cause)-[r:CAUSES {rca_type: p.rca_type, period: p.period}]->(target)
SET r.contribution_score = p.contribution_score,
    r.confidence = p.confidence,
    r.period = p.period,
    r.timestamp = p.timestamp
RETURN count(r) AS updated
"""


class RCAIntegrationLayer:
    """
    Persists Root Cause Analysis causal chains and contribution scores into Neo4j relationships.
    Increments graph version in _GraphMeta.
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def sync_rca(
        self,
        rca_report: dict[str, Any],
        timestamp: str | None = None,
        period: str | None = None,
    ) -> dict[str, Any]:
        """
        Write :CAUSES relationships into Neo4j.
        No contributors → write nothing and return updated_relationships: 0.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        report = rca_report.get("report", rca_report)
        contributors = report.get("risk_contributors", [])
        target_id = report.get("target_id", "")
        rca_type = report.get("rca_type", "late_delivery")

        if not contributors or not target_id:
            return {"updated_relationships": 0, "timestamp": ts}

        batch = [
            {
                "cause_id": str(c.get("entity_id", c.get("node_id", ""))),
                "target_id": str(target_id),
                "rca_type": str(rca_type),
                "period": period or "",
                "contribution_score": float(c.get("score", c.get("contribution_score", 0.0))),
                "confidence": float(c.get("confidence", 0.0)),
                "timestamp": ts,
            }
            for c in contributors
            if c.get("entity_id") or c.get("node_id")
        ]

        if not batch:
            return {"updated_relationships": 0, "timestamp": ts}

        updated = 0
        records = await self._conn.execute_write(_CREATE_RCA_CAUSES_RELATIONSHIP, {"batch": batch})
        updated = records[0]["updated"] if records else 0

        meta_query = """
            MERGE (meta:_GraphMeta {key: 'active_version'})
            ON CREATE SET meta.version = 1, meta.updated_at = $ts, meta.last_trigger = 'root_cause'
            ON MATCH SET meta.version = coalesce(meta.version, 0) + 1, meta.updated_at = $ts, meta.last_trigger = 'root_cause'
            RETURN meta.version AS version
        """
        await self._conn.execute_write(meta_query, {"ts": ts})

        logger.info(f"[RCAIntegration] Created/updated {updated} :CAUSES relationships (period={period}, ts={ts})")
        return {"updated_relationships": updated, "timestamp": ts}


async def auto_sync_rca(rca_report: dict[str, Any] | None = None, period: str | None = None) -> dict[str, Any]:
    """Post-RCA analysis auto-sync hook."""
    if not rca_report:
        return {"updated_relationships": 0}
    layer = RCAIntegrationLayer()
    return await layer.sync_rca(rca_report, period=period)

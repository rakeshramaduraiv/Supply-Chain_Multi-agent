"""
RCA Feedback Service (Issue #7)
=================================
Stores user corrections on RCA analyses and adjusts TPKE edge confidence
so the graph learns from mistakes.

Feedback flow:
  User submits {correct: False, actual_cause: "Weather delay"}
    -> feedback saved to PostgreSQL rca_feedback table
    -> TPKE edges used by that RCA have confidence reduced by 0.2
    -> if confidence < 0.5, edge demoted back to CANDIDATE

  User submits {correct: True}
    -> TPKE edges used by that RCA have confidence increased by 0.1
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Confidence adjustments
_POSITIVE_DELTA = 0.10   # User confirmed RCA was correct
_NEGATIVE_DELTA = 0.20   # User said RCA was wrong
_DEMOTION_THRESHOLD = 0.50  # Below this, edge reverts to CANDIDATE


class RCAFeedbackService:
    """
    Handles user feedback on RCA results and propagates corrections
    to TPKE edge confidence scores.
    """

    def __init__(self, db_session: Any = None, neo4j_conn: Any = None):
        self._db = db_session
        self._conn = neo4j_conn

    async def submit_feedback(
        self,
        rca_id: str,
        correct: bool,
        actual_cause: str | None = None,
        notes: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Record user feedback and adjust TPKE edge confidence.

        Returns a summary dict with feedback_id and confidence_impact.
        """
        feedback_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Persist to PostgreSQL if session available
        if self._db is not None:
            try:
                await self._db.execute(
                    """
                    INSERT INTO rca_feedback
                        (id, rca_id, user_id, was_correct, actual_cause, notes, created_at)
                    VALUES
                        (:id, :rca_id, :user_id, :was_correct, :actual_cause, :notes, :now)
                    """,
                    {
                        "id": feedback_id,
                        "rca_id": rca_id,
                        "user_id": user_id or "anonymous",
                        "was_correct": correct,
                        "actual_cause": actual_cause,
                        "notes": notes,
                        "now": now,
                    },
                )
                await self._db.commit()
            except Exception as e:
                logger.warning(f"RCA feedback DB write failed: {e}")

        # Adjust TPKE edge confidence in Neo4j
        delta = _POSITIVE_DELTA if correct else -_NEGATIVE_DELTA
        confidence_impact = await self._adjust_tpke_edges(rca_id, delta)

        logger.info(
            f"RCA feedback recorded: rca_id={rca_id} correct={correct} "
            f"delta={delta:+.2f} impact={confidence_impact:.4f}"
        )

        return {
            "status": "feedback_recorded",
            "rca_id": rca_id,
            "feedback_id": feedback_id,
            "confidence_impact": round(confidence_impact, 4),
        }

    async def get_feedback_summary(self, rca_id: str) -> dict[str, Any]:
        """Return aggregated feedback stats for an RCA."""
        if self._db is None:
            return {"rca_id": rca_id, "feedback_count": 0}

        try:
            rows = await self._db.execute(
                "SELECT was_correct, actual_cause, notes, created_at "
                "FROM rca_feedback WHERE rca_id = :rca_id",
                {"rca_id": rca_id},
            )
            records = rows.fetchall() if hasattr(rows, "fetchall") else []
        except Exception:
            records = []

        total = len(records)
        correct = sum(1 for r in records if r[0])
        return {
            "rca_id": rca_id,
            "feedback_count": total,
            "correct": correct,
            "incorrect": total - correct,
            "accuracy_percent": round(correct / total * 100, 1) if total else 0.0,
        }

    async def _adjust_tpke_edges(self, rca_id: str, delta: float) -> float:
        """
        Adjust confidence of TPKE edges associated with this RCA.
        Demotes edges below _DEMOTION_THRESHOLD back to CANDIDATE.
        Returns mean absolute change applied.
        """
        if self._conn is None:
            return 0.0

        # Find TPKE edges linked to this RCA report
        find_cypher = """
            MATCH (rca:RootCauseEvent {report_id: $rca_id})-[:RCA_AFFECTS_TARGET]->(target)
            MATCH (src)-[r:TPKE_INFERRED]->(target)
            RETURN r.relationship_type AS rel_type,
                   src.entity_id AS src_id,
                   target.entity_id AS tgt_id,
                   coalesce(r.confidence, 0.5) AS confidence
        """
        try:
            edges = await self._conn.execute_query(find_cypher, {"rca_id": rca_id})
        except Exception as e:
            logger.warning(f"TPKE edge lookup failed for rca_id={rca_id}: {e}")
            return 0.0

        if not edges:
            return 0.0

        total_change = 0.0
        for edge in edges:
            old_conf = float(edge.get("confidence", 0.5))
            new_conf = max(0.0, min(1.0, old_conf + delta))
            new_status = "CANDIDATE" if new_conf < _DEMOTION_THRESHOLD else "ACTIVE"
            total_change += abs(new_conf - old_conf)

            update_cypher = """
                MATCH (s {entity_id: $src_id})-[r:TPKE_INFERRED]->(t {entity_id: $tgt_id})
                WHERE r.relationship_type = $rel_type
                SET r.confidence = $confidence, r.status = $status
            """
            try:
                await self._conn.execute_write(
                    update_cypher,
                    {
                        "src_id": edge["src_id"],
                        "tgt_id": edge["tgt_id"],
                        "rel_type": edge["rel_type"],
                        "confidence": round(new_conf, 4),
                        "status": new_status,
                    },
                )
            except Exception as e:
                logger.warning(f"TPKE confidence update failed: {e}")

        return total_change / len(edges)

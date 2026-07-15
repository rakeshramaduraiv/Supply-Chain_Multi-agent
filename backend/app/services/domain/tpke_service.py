"""TPKE Log Service - Temporal Pattern Knowledge Evolution tracking."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import TPKELogRepository
from app.services import BaseService


class TPKELogService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = TPKELogRepository(session)

    async def log_mutation(
        self,
        action: str,
        source_node_id: str,
        source_node_type: str,
        target_node_id: str,
        target_node_type: str,
        relationship_type: str,
        confidence_before: float | None = None,
        confidence_after: float | None = None,
        frequency: int = 1,
        evidence: dict | None = None,
        graph_version_id: str | None = None,
        triggered_by: str = "system",
    ) -> dict:
        log = await self.repo.create(
            action=action,
            source_node_id=source_node_id,
            source_node_type=source_node_type,
            target_node_id=target_node_id,
            target_node_type=target_node_type,
            relationship_type=relationship_type,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            frequency=frequency,
            evidence_json=evidence,
            graph_version_id=graph_version_id,
            triggered_by=triggered_by,
        )
        return {"id": log.id, "action": action}

    async def get_node_history(self, node_id: str) -> list[dict]:
        logs = await self.repo.get_by_node(node_id)
        return [
            {"id": l.id, "action": l.action, "relationship_type": l.relationship_type, "confidence_after": l.confidence_after, "created_at": str(l.created_at)}
            for l in logs
        ]

    async def get_action_summary(self) -> dict[str, int]:
        return await self.repo.count_by_action()

    async def get_recent_mutations(self, since: datetime, limit: int = 100) -> list[dict]:
        logs = await self.repo.get_recent(since, limit)
        return [
            {"id": l.id, "action": l.action, "source": f"{l.source_node_type}:{l.source_node_id}", "target": f"{l.target_node_type}:{l.target_node_id}", "confidence_after": l.confidence_after}
            for l in logs
        ]

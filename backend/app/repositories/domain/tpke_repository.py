"""TPKE Log Repository."""

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import TPKELog
from app.repositories import BaseRepository


class TPKELogRepository(BaseRepository[TPKELog]):
    def __init__(self, session: AsyncSession):
        super().__init__(TPKELog, session)

    async def get_by_action(self, action: str, skip: int = 0, limit: int = 100) -> list[TPKELog]:
        stmt = (
            select(TPKELog)
            .where(TPKELog.action == action)
            .order_by(TPKELog.created_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_node(self, node_id: str) -> list[TPKELog]:
        stmt = (
            select(TPKELog)
            .where((TPKELog.source_node_id == node_id) | (TPKELog.target_node_id == node_id))
            .order_by(TPKELog.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_graph_version(self, graph_version_id: str) -> list[TPKELog]:
        stmt = (
            select(TPKELog)
            .where(TPKELog.graph_version_id == graph_version_id)
            .order_by(TPKELog.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_action(self) -> dict[str, int]:
        stmt = (
            select(TPKELog.action, func.count())
            .group_by(TPKELog.action)
        )
        result = await self.session.execute(stmt)
        return dict(result.all())

    async def get_recent(self, since: datetime, limit: int = 100) -> list[TPKELog]:
        stmt = (
            select(TPKELog)
            .where(TPKELog.created_at >= since)
            .order_by(TPKELog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

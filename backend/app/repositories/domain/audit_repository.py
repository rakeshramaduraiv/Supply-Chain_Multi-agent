"""Audit Log Repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AuditLog
from app.repositories import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def get_by_user(self, user_id: str, skip: int = 0, limit: int = 100) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_resource(self, resource_type: str, resource_id: str | None = None) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        stmt = stmt.order_by(AuditLog.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_in_range(self, start: datetime, end: datetime, skip: int = 0, limit: int = 500) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.created_at >= start, AuditLog.created_at <= end)
            .order_by(AuditLog.created_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        status: str = "success",
    ) -> AuditLog:
        return await self.create(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            details_json=details,
            ip_address=ip_address,
            status=status,
        )

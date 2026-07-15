"""Audit Service - Action logging and audit trail."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import AuditLogRepository
from app.services import BaseService


class AuditService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = AuditLogRepository(session)

    async def log(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        user_id: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        status: str = "success",
    ) -> dict:
        entry = await self.repo.log_action(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            details=details,
            ip_address=ip_address,
            status=status,
        )
        return {"id": entry.id, "action": action}

    async def get_user_activity(self, user_id: str, skip: int = 0, limit: int = 100) -> list[dict]:
        logs = await self.repo.get_by_user(user_id, skip=skip, limit=limit)
        return [
            {"id": l.id, "action": l.action, "resource_type": l.resource_type, "status": l.status, "created_at": str(l.created_at)}
            for l in logs
        ]

    async def get_resource_history(self, resource_type: str, resource_id: str | None = None) -> list[dict]:
        logs = await self.repo.get_by_resource(resource_type, resource_id)
        return [
            {"id": l.id, "action": l.action, "user_id": l.user_id, "status": l.status, "created_at": str(l.created_at)}
            for l in logs
        ]

    async def get_in_range(self, start: datetime, end: datetime, skip: int = 0, limit: int = 500) -> list[dict]:
        logs = await self.repo.get_in_range(start, end, skip=skip, limit=limit)
        return [
            {"id": l.id, "action": l.action, "resource_type": l.resource_type, "user_id": l.user_id, "created_at": str(l.created_at)}
            for l in logs
        ]

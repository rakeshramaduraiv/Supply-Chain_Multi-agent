"""Notification Service - User notification management."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import NotificationRepository
from app.services import BaseService


class NotificationService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = NotificationRepository(session)

    async def send(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str = "info",
        priority: str = "normal",
        resource_type: str | None = None,
        resource_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict:
        n = await self.repo.create(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            resource_type=resource_type,
            resource_id=resource_id,
            expires_at=expires_at,
        )
        return {"id": n.id, "title": title}

    async def get_for_user(self, user_id: str, unread_only: bool = False, skip: int = 0, limit: int = 50) -> list[dict]:
        notifications = await self.repo.get_for_user(user_id, unread_only=unread_only, skip=skip, limit=limit)
        return [
            {"id": n.id, "title": n.title, "message": n.message, "type": n.notification_type, "priority": n.priority, "is_read": n.is_read, "created_at": str(n.created_at)}
            for n in notifications
        ]

    async def unread_count(self, user_id: str) -> int:
        return await self.repo.unread_count(user_id)

    async def mark_read(self, notification_id: str) -> None:
        await self.repo.mark_read(notification_id)

    async def mark_all_read(self, user_id: str) -> int:
        return await self.repo.mark_all_read(user_id)

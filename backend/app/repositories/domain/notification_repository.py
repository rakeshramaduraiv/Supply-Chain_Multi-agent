"""Notification Repository."""

from datetime import datetime, timezone

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Notification
from app.repositories import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, session: AsyncSession):
        super().__init__(Notification, session)

    async def get_for_user(self, user_id: str, unread_only: bool = False, skip: int = 0, limit: int = 50) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)
        stmt = stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def unread_count(self, user_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def mark_read(self, notification_id: str) -> None:
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def mark_all_read(self, user_id: str) -> int:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

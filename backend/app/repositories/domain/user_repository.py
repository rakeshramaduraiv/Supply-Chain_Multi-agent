"""User Repository."""

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import User
from app.repositories import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username, User.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_users(self, skip: int = 0, limit: int = 50) -> list[User]:
        stmt = (
            select(User)
            .where(User.is_active == True, User.is_deleted == False)
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_last_login(self, user_id: str) -> None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def deactivate(self, user_id: str) -> None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(is_active=False)
        )
        await self.session.execute(stmt)
        await self.session.flush()

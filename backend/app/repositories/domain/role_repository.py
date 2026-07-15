"""Role Repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Role
from app.repositories import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session: AsyncSession):
        super().__init__(Role, session)

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_roles(self) -> list[Role]:
        stmt = select(Role).where(Role.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

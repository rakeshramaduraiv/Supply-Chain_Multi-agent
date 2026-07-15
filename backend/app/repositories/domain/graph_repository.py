"""Graph Version Repository."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import GraphVersion
from app.repositories import BaseRepository


class GraphVersionRepository(BaseRepository[GraphVersion]):
    def __init__(self, session: AsyncSession):
        super().__init__(GraphVersion, session)

    async def get_active(self) -> GraphVersion | None:
        stmt = select(GraphVersion).where(GraphVersion.is_active == True).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest(self) -> GraphVersion | None:
        stmt = select(GraphVersion).order_by(GraphVersion.version.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_next_version_number(self) -> int:
        latest = await self.get_latest()
        return (latest.version + 1) if latest else 1

    async def activate_version(self, version_id: str) -> None:
        """Deactivate all, then activate specified version."""
        await self.session.execute(
            update(GraphVersion).values(is_active=False)
        )
        await self.session.execute(
            update(GraphVersion).where(GraphVersion.id == version_id).values(is_active=True, status="active")
        )
        await self.session.flush()

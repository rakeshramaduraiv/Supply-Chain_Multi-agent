"""Feature Registry Repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import FeatureRegistry
from app.repositories import BaseRepository


class FeatureRepository(BaseRepository[FeatureRegistry]):
    def __init__(self, session: AsyncSession):
        super().__init__(FeatureRegistry, session)

    async def get_active_features(self) -> list[FeatureRegistry]:
        stmt = (
            select(FeatureRegistry)
            .where(FeatureRegistry.is_active == True)
            .order_by(FeatureRegistry.importance_score.desc().nullslast())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, name: str) -> FeatureRegistry | None:
        stmt = (
            select(FeatureRegistry)
            .where(FeatureRegistry.name == name)
            .order_by(FeatureRegistry.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_type(self, feature_type: str) -> list[FeatureRegistry]:
        stmt = (
            select(FeatureRegistry)
            .where(FeatureRegistry.feature_type == feature_type, FeatureRegistry.is_active == True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_top_features(self, limit: int = 10) -> list[FeatureRegistry]:
        stmt = (
            select(FeatureRegistry)
            .where(FeatureRegistry.is_active == True, FeatureRegistry.importance_score.isnot(None))
            .order_by(FeatureRegistry.importance_score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

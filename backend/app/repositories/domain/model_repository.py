"""Trained Model Repository."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import TrainedModel
from app.repositories import BaseRepository


class TrainedModelRepository(BaseRepository[TrainedModel]):
    def __init__(self, session: AsyncSession):
        super().__init__(TrainedModel, session)

    async def get_active_model(self, name: str) -> TrainedModel | None:
        stmt = (
            select(TrainedModel)
            .where(TrainedModel.name == name, TrainedModel.is_active == True)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_version(self, name: str) -> TrainedModel | None:
        stmt = (
            select(TrainedModel)
            .where(TrainedModel.name == name)
            .order_by(TrainedModel.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_active(self) -> list[TrainedModel]:
        stmt = select(TrainedModel).where(TrainedModel.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def activate_version(self, model_id: str, name: str) -> None:
        """Deactivate all versions of a model, then activate the specified one."""
        await self.session.execute(
            update(TrainedModel).where(TrainedModel.name == name).values(is_active=False)
        )
        await self.session.execute(
            update(TrainedModel).where(TrainedModel.id == model_id).values(is_active=True, status="active")
        )
        await self.session.flush()

    async def get_by_type(self, model_type: str) -> list[TrainedModel]:
        stmt = (
            select(TrainedModel)
            .where(TrainedModel.model_type == model_type)
            .order_by(TrainedModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

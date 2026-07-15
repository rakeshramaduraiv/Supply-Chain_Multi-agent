"""Forecast Run & Result Repositories."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import ForecastRun, ForecastResult
from app.repositories import BaseRepository


class ForecastRunRepository(BaseRepository[ForecastRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(ForecastRun, session)

    async def get_by_status(self, status: str, skip: int = 0, limit: int = 50) -> list[ForecastRun]:
        stmt = (
            select(ForecastRun)
            .where(ForecastRun.status == status)
            .order_by(ForecastRun.created_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(self) -> ForecastRun | None:
        stmt = select(ForecastRun).order_by(ForecastRun.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_dataset(self, dataset_id: str) -> list[ForecastRun]:
        stmt = (
            select(ForecastRun)
            .where(ForecastRun.dataset_id == dataset_id)
            .order_by(ForecastRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ForecastResultRepository(BaseRepository[ForecastResult]):
    def __init__(self, session: AsyncSession):
        super().__init__(ForecastResult, session)

    async def get_by_run(self, run_id: str, skip: int = 0, limit: int = 1000) -> list[ForecastResult]:
        stmt = (
            select(ForecastResult)
            .where(ForecastResult.forecast_run_id == run_id)
            .order_by(ForecastResult.forecast_date)
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_risk_flagged(self, run_id: str) -> list[ForecastResult]:
        stmt = (
            select(ForecastResult)
            .where(ForecastResult.forecast_run_id == run_id, ForecastResult.risk_flag == True)
            .order_by(ForecastResult.confidence_score.desc().nullslast())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_entity(self, entity_id: str, entity_type: str) -> list[ForecastResult]:
        stmt = (
            select(ForecastResult)
            .where(ForecastResult.entity_id == entity_id, ForecastResult.entity_type == entity_type)
            .order_by(ForecastResult.forecast_date.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_run(self, run_id: str) -> int:
        stmt = select(func.count()).select_from(ForecastResult).where(ForecastResult.forecast_run_id == run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

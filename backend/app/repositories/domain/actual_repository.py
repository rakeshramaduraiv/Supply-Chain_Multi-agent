"""Actual Upload Repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import ActualUpload
from app.repositories import BaseRepository


class ActualUploadRepository(BaseRepository[ActualUpload]):
    def __init__(self, session: AsyncSession):
        super().__init__(ActualUpload, session)

    async def get_by_forecast_run(self, forecast_run_id: str) -> list[ActualUpload]:
        stmt = (
            select(ActualUpload)
            .where(ActualUpload.forecast_run_id == forecast_run_id)
            .order_by(ActualUpload.period_start.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> list[ActualUpload]:
        stmt = (
            select(ActualUpload)
            .where(ActualUpload.status == status)
            .order_by(ActualUpload.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_comparison(self) -> ActualUpload | None:
        stmt = (
            select(ActualUpload)
            .where(ActualUpload.status == "compared")
            .order_by(ActualUpload.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

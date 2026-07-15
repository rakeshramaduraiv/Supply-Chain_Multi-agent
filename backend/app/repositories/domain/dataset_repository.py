"""Dataset Repository."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Dataset
from app.repositories import BaseRepository


class DatasetRepository(BaseRepository[Dataset]):
    def __init__(self, session: AsyncSession):
        super().__init__(Dataset, session)

    async def get_by_type(self, dataset_type: str, skip: int = 0, limit: int = 50) -> list[Dataset]:
        stmt = (
            select(Dataset)
            .where(Dataset.dataset_type == dataset_type, Dataset.is_deleted == False)
            .order_by(Dataset.created_at.desc())
            .offset(skip).limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(self, status: str) -> list[Dataset]:
        stmt = (
            select(Dataset)
            .where(Dataset.status == status, Dataset.is_deleted == False)
            .order_by(Dataset.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(self, dataset_type: str | None = None) -> Dataset | None:
        stmt = select(Dataset).where(Dataset.is_deleted == False)
        if dataset_type:
            stmt = stmt.where(Dataset.dataset_type == dataset_type)
        stmt = stmt.order_by(Dataset.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def total_size_bytes(self) -> int:
        stmt = select(func.coalesce(func.sum(Dataset.file_size_bytes), 0)).where(Dataset.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one()

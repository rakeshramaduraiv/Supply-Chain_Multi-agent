"""
AMASCI Base Repository
=======================
Generic CRUD repository pattern for all database operations.
"""

import logging
from typing import Any, Generic, Type, TypeVar

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

logger = logging.getLogger(__name__)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing CRUD operations.

    All concrete repositories inherit from this base.
    Business logic must NOT exist in repositories.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        logger.debug(f"Created {self.model.__name__} with id={getattr(instance, 'id', 'N/A')}")
        return instance

    async def get_by_id(self, record_id: str) -> ModelType | None:
        """Retrieve a record by primary key."""
        stmt = select(self.model).where(self.model.id == record_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> list[ModelType]:
        """Retrieve multiple records with pagination and optional filters."""
        stmt = select(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    stmt = stmt.where(getattr(self.model, key) == value)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count records with optional filters."""
        stmt = select(func.count()).select_from(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    stmt = stmt.where(getattr(self.model, key) == value)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update_by_id(self, record_id: str, **kwargs: Any) -> ModelType | None:
        """Update a record by primary key."""
        stmt = (
            update(self.model)
            .where(self.model.id == record_id)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        instance = result.scalar_one_or_none()
        if instance:
            logger.debug(f"Updated {self.model.__name__} id={record_id}")
        return instance

    async def delete_by_id(self, record_id: str) -> bool:
        """Soft-delete a record if SoftDeleteMixin is present, else hard delete."""
        instance = await self.get_by_id(record_id)
        if not instance:
            return False

        if hasattr(instance, "is_deleted"):
            from datetime import datetime, timezone
            instance.is_deleted = True
            instance.deleted_at = datetime.now(timezone.utc)
        else:
            await self.session.delete(instance)

        await self.session.flush()
        logger.debug(f"Deleted {self.model.__name__} id={record_id}")
        return True

    async def exists(self, record_id: str) -> bool:
        """Check if a record exists."""
        stmt = select(func.count()).select_from(self.model).where(self.model.id == record_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

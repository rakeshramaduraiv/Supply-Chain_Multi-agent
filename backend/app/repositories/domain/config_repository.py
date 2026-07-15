"""System Configuration Repository."""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import SystemConfiguration
from app.repositories import BaseRepository


class SystemConfigRepository(BaseRepository[SystemConfiguration]):
    def __init__(self, session: AsyncSession):
        super().__init__(SystemConfiguration, session)

    async def get_by_key(self, key: str) -> SystemConfiguration | None:
        stmt = select(SystemConfiguration).where(SystemConfiguration.key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_value(self, key: str, default: Any = None) -> Any:
        config = await self.get_by_key(key)
        if not config:
            return default
        return self._cast_value(config.value, config.value_type)

    async def set_value(self, key: str, value: Any, value_type: str = "string", category: str = "general", description: str | None = None) -> SystemConfiguration:
        existing = await self.get_by_key(key)
        str_value = json.dumps(value) if value_type == "json" else str(value)
        if existing:
            existing.value = str_value
            existing.value_type = value_type
            await self.session.flush()
            return existing
        return await self.create(key=key, value=str_value, value_type=value_type, category=category, description=description)

    async def get_by_category(self, category: str) -> list[SystemConfiguration]:
        stmt = select(SystemConfiguration).where(SystemConfiguration.category == category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _cast_value(value: str, value_type: str) -> Any:
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            return json.loads(value)
        return value

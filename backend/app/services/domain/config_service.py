"""System Configuration Service - Key-value config management."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import SystemConfigRepository
from app.services import BaseService


class SystemConfigService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = SystemConfigRepository(session)

    async def get(self, key: str, default: Any = None) -> Any:
        return await self.repo.get_value(key, default)

    async def set(self, key: str, value: Any, value_type: str = "string", category: str = "general", description: str | None = None) -> dict:
        config = await self.repo.set_value(key, value, value_type, category, description)
        return {"key": config.key, "value": config.value, "category": config.category}

    async def get_category(self, category: str) -> list[dict]:
        configs = await self.repo.get_by_category(category)
        return [
            {"key": c.key, "value": c.value if not c.is_sensitive else "***", "value_type": c.value_type, "description": c.description}
            for c in configs
        ]

    async def get_all_non_sensitive(self) -> list[dict]:
        configs = await self.repo.get_all(limit=500)
        return [
            {"key": c.key, "value": c.value if not c.is_sensitive else "***", "category": c.category, "value_type": c.value_type}
            for c in configs
        ]

    async def delete(self, key: str) -> bool:
        config = await self.repo.get_by_key(key)
        if not config:
            return False
        return await self.repo.delete_by_id(config.id)

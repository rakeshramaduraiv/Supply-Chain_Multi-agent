"""Role Service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import RoleRepository
from app.services import BaseService


class RoleService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = RoleRepository(session)

    async def get_all(self) -> list[dict]:
        roles = await self.repo.get_active_roles()
        return [{"id": r.id, "name": r.name, "description": r.description, "permissions": r.permissions} for r in roles]

    async def get_by_name(self, name: str) -> dict | None:
        role = await self.repo.get_by_name(name)
        if not role:
            return None
        return {"id": role.id, "name": role.name, "description": role.description, "permissions": role.permissions}

    async def create_role(self, name: str, description: str | None = None, permissions: dict | None = None) -> dict:
        existing = await self.repo.get_by_name(name)
        if existing:
            raise ValueError(f"Role '{name}' already exists")
        role = await self.repo.create(name=name, description=description, permissions=permissions)
        return {"id": role.id, "name": role.name}

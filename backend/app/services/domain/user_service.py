"""User Service - Authentication and user management."""

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import UserRepository, RoleRepository
from app.services import BaseService


class UserService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.session = session

    async def create_user(self, email: str, username: str, password: str, role_name: str = "viewer", full_name: str | None = None) -> dict:
        self._log_start("create_user", email=email)
        existing = await self.repo.get_by_email(email)
        if existing:
            raise ValueError(f"User with email {email} already exists")

        role = await self.role_repo.get_by_name(role_name)
        if not role:
            raise ValueError(f"Role '{role_name}' not found")

        hashed = self._hash_password(password)
        user = await self.repo.create(
            email=email,
            username=username,
            hashed_password=hashed,
            full_name=full_name,
            role_id=role.id,
        )
        return {"id": user.id, "email": user.email, "username": user.username, "role": role_name}

    async def authenticate(self, email: str, password: str) -> dict | None:
        user = await self.repo.get_by_email(email)
        if not user or not user.is_active:
            return None
        if not self._verify_password(password, user.hashed_password):
            return None
        await self.repo.update_last_login(user.id)
        return {"id": user.id, "email": user.email, "username": user.username, "role": user.role.name}

    async def get_user(self, user_id: str) -> dict | None:
        user = await self.repo.get_by_id(user_id)
        if not user or user.is_deleted:
            return None
        return {"id": user.id, "email": user.email, "username": user.username, "full_name": user.full_name, "role": user.role.name, "is_active": user.is_active}

    async def list_users(self, skip: int = 0, limit: int = 50) -> list[dict]:
        users = await self.repo.get_active_users(skip=skip, limit=limit)
        return [{"id": u.id, "email": u.email, "username": u.username, "role": u.role.name} for u in users]

    async def deactivate_user(self, user_id: str) -> bool:
        await self.repo.deactivate(user_id)
        return True

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return f"{salt}:{hashed.hex()}"

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        salt, hash_hex = hashed.split(":")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return check.hex() == hash_hex

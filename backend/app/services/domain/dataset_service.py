"""Dataset Service - Upload, profiling, and lifecycle management."""

import hashlib
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import DatasetRepository
from app.services import BaseService


class DatasetService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = DatasetRepository(session)

    async def register_dataset(
        self,
        name: str,
        filename: str,
        file_path: str,
        dataset_type: str,
        file_size_bytes: int,
        row_count: int | None = None,
        column_count: int | None = None,
        uploaded_by: str | None = None,
        checksum: str | None = None,
    ) -> dict:
        self._log_start("register_dataset", filename=filename)
        dataset = await self.repo.create(
            name=name,
            filename=filename,
            file_path=file_path,
            dataset_type=dataset_type,
            file_size_bytes=file_size_bytes,
            row_count=row_count,
            column_count=column_count,
            uploaded_by=uploaded_by,
            checksum=checksum,
        )
        return {"id": dataset.id, "name": dataset.name, "status": dataset.status}

    async def update_status(self, dataset_id: str, status: str, **kwargs) -> dict | None:
        dataset = await self.repo.update_by_id(dataset_id, status=status, **kwargs)
        if not dataset:
            return None
        return {"id": dataset.id, "status": dataset.status}

    async def get_dataset(self, dataset_id: str) -> dict | None:
        d = await self.repo.get_by_id(dataset_id)
        if not d or d.is_deleted:
            return None
        return {
            "id": d.id, "name": d.name, "filename": d.filename, "dataset_type": d.dataset_type,
            "status": d.status, "row_count": d.row_count, "column_count": d.column_count,
            "quality_score": d.quality_score, "file_size_bytes": d.file_size_bytes, "created_at": str(d.created_at),
        }

    async def list_datasets(self, dataset_type: str | None = None, skip: int = 0, limit: int = 50) -> list[dict]:
        if dataset_type:
            datasets = await self.repo.get_by_type(dataset_type, skip=skip, limit=limit)
        else:
            datasets = await self.repo.get_all(skip=skip, limit=limit, filters={"is_deleted": False})
        return [{"id": d.id, "name": d.name, "dataset_type": d.dataset_type, "status": d.status, "row_count": d.row_count} for d in datasets]

    async def get_latest(self, dataset_type: str | None = None) -> dict | None:
        d = await self.repo.get_latest(dataset_type)
        if not d:
            return None
        return {"id": d.id, "name": d.name, "status": d.status, "row_count": d.row_count}

    async def delete_dataset(self, dataset_id: str) -> bool:
        return await self.repo.delete_by_id(dataset_id)

    @staticmethod
    def compute_checksum(file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

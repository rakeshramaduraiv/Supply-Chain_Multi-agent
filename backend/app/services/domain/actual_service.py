"""Actual Upload Service - Forecast vs actuals comparison."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import ActualUploadRepository
from app.services import BaseService


class ActualUploadService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = ActualUploadRepository(session)

    async def create_upload(
        self,
        dataset_id: str,
        period_start: datetime,
        period_end: datetime,
        total_records: int,
        forecast_run_id: str | None = None,
        uploaded_by: str | None = None,
    ) -> dict:
        upload = await self.repo.create(
            dataset_id=dataset_id,
            forecast_run_id=forecast_run_id,
            period_start=period_start,
            period_end=period_end,
            total_records=total_records,
            uploaded_by=uploaded_by,
        )
        return {"id": upload.id, "status": upload.status}

    async def record_comparison(
        self,
        upload_id: str,
        matched_records: int,
        mape: float | None = None,
        rmse: float | None = None,
        bias: float | None = None,
        accuracy_pct: float | None = None,
        comparison_json: dict | None = None,
    ) -> dict:
        upload = await self.repo.update_by_id(
            upload_id,
            status="compared",
            matched_records=matched_records,
            mape=mape,
            rmse=rmse,
            bias=bias,
            accuracy_pct=accuracy_pct,
            comparison_json=comparison_json,
        )
        return {"id": upload_id, "status": "compared", "accuracy_pct": accuracy_pct}

    async def get_upload(self, upload_id: str) -> dict | None:
        u = await self.repo.get_by_id(upload_id)
        if not u:
            return None
        return {
            "id": u.id, "dataset_id": u.dataset_id, "period_start": str(u.period_start),
            "period_end": str(u.period_end), "status": u.status, "accuracy_pct": u.accuracy_pct,
            "mape": u.mape, "rmse": u.rmse, "total_records": u.total_records,
        }

    async def get_latest_comparison(self) -> dict | None:
        u = await self.repo.get_latest_comparison()
        if not u:
            return None
        return {"id": u.id, "accuracy_pct": u.accuracy_pct, "mape": u.mape, "period_start": str(u.period_start)}

    async def list_uploads(self, status: str | None = None) -> list[dict]:
        if status:
            uploads = await self.repo.get_by_status(status)
        else:
            uploads = await self.repo.get_all(limit=100)
        return [{"id": u.id, "status": u.status, "total_records": u.total_records, "accuracy_pct": u.accuracy_pct} for u in uploads]

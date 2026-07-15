"""Forecast Service - Run management and result retrieval."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import ForecastRunRepository, ForecastResultRepository
from app.services import BaseService


class ForecastService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.run_repo = ForecastRunRepository(session)
        self.result_repo = ForecastResultRepository(session)

    async def create_run(
        self,
        name: str,
        dataset_id: str,
        model_id: str,
        horizon_days: int = 30,
        parameters: dict | None = None,
        triggered_by: str | None = None,
    ) -> dict:
        run = await self.run_repo.create(
            name=name,
            dataset_id=dataset_id,
            model_id=model_id,
            forecast_horizon_days=horizon_days,
            parameters_json=parameters,
            triggered_by=triggered_by,
            status="pending",
        )
        return {"id": run.id, "name": run.name, "status": run.status}

    async def complete_run(self, run_id: str, total_predictions: int, avg_confidence: float, duration_ms: float) -> dict:
        run = await self.run_repo.update_by_id(
            run_id,
            status="completed",
            total_predictions=total_predictions,
            avg_confidence=avg_confidence,
            duration_ms=duration_ms,
        )
        return {"id": run_id, "status": "completed", "total_predictions": total_predictions}

    async def fail_run(self, run_id: str, error: str) -> None:
        await self.run_repo.update_by_id(run_id, status="failed", error_message=error)

    async def add_results(self, run_id: str, results: list[dict]) -> int:
        for r in results:
            await self.result_repo.create(forecast_run_id=run_id, **r)
        return len(results)

    async def get_run(self, run_id: str) -> dict | None:
        run = await self.run_repo.get_by_id(run_id)
        if not run:
            return None
        return {
            "id": run.id, "name": run.name, "status": run.status,
            "total_predictions": run.total_predictions, "avg_confidence": run.avg_confidence,
            "forecast_horizon_days": run.forecast_horizon_days, "duration_ms": run.duration_ms,
            "created_at": str(run.created_at),
        }

    async def list_runs(self, status: str | None = None, skip: int = 0, limit: int = 50) -> list[dict]:
        if status:
            runs = await self.run_repo.get_by_status(status, skip=skip, limit=limit)
        else:
            runs = await self.run_repo.get_all(skip=skip, limit=limit)
        return [{"id": r.id, "name": r.name, "status": r.status, "created_at": str(r.created_at)} for r in runs]

    async def get_results(self, run_id: str, skip: int = 0, limit: int = 1000) -> list[dict]:
        results = await self.result_repo.get_by_run(run_id, skip=skip, limit=limit)
        return [
            {
                "id": r.id, "entity_id": r.entity_id, "entity_type": r.entity_type,
                "forecast_date": str(r.forecast_date), "predicted_value": r.predicted_value,
                "confidence_score": r.confidence_score, "risk_flag": r.risk_flag,
            }
            for r in results
        ]

    async def get_risk_alerts(self, run_id: str) -> list[dict]:
        results = await self.result_repo.get_risk_flagged(run_id)
        return [
            {"entity_id": r.entity_id, "entity_type": r.entity_type, "predicted_value": r.predicted_value, "confidence_score": r.confidence_score}
            for r in results
        ]

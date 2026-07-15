"""Trained Model Service - Model lifecycle and version management."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import TrainedModelRepository
from app.services import BaseService


class TrainedModelService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = TrainedModelRepository(session)

    async def register_model(
        self,
        name: str,
        model_type: str,
        file_path: str,
        dataset_id: str | None = None,
        hyperparameters: dict | None = None,
        trained_by: str = "system",
    ) -> dict:
        latest = await self.repo.get_latest_version(name)
        version = (latest.version + 1) if latest else 1
        model = await self.repo.create(
            name=name,
            model_type=model_type,
            version=version,
            file_path=file_path,
            dataset_id=dataset_id,
            hyperparameters_json=hyperparameters,
            trained_by=trained_by,
            status="training",
        )
        return {"id": model.id, "name": model.name, "version": model.version}

    async def complete_training(self, model_id: str, metrics: dict, activate: bool = True) -> dict:
        update_data = {
            "status": "active" if activate else "trained",
            "accuracy": metrics.get("accuracy"),
            "precision_score": metrics.get("precision"),
            "recall_score": metrics.get("recall"),
            "f1_score": metrics.get("f1"),
            "rmse": metrics.get("rmse"),
            "mae": metrics.get("mae"),
            "training_duration_ms": metrics.get("duration_ms"),
            "training_rows": metrics.get("training_rows"),
            "feature_importance_json": metrics.get("feature_importance"),
        }
        model = await self.repo.update_by_id(model_id, **{k: v for k, v in update_data.items() if v is not None})
        if activate and model:
            await self.repo.activate_version(model_id, model.name)
        return {"id": model_id, "status": "active" if activate else "trained"}

    async def get_active_models(self) -> list[dict]:
        models = await self.repo.get_all_active()
        return [
            {"id": m.id, "name": m.name, "model_type": m.model_type, "version": m.version, "accuracy": m.accuracy}
            for m in models
        ]

    async def get_model(self, model_id: str) -> dict | None:
        m = await self.repo.get_by_id(model_id)
        if not m:
            return None
        return {
            "id": m.id, "name": m.name, "model_type": m.model_type, "version": m.version,
            "status": m.status, "accuracy": m.accuracy, "f1_score": m.f1_score,
            "training_duration_ms": m.training_duration_ms, "is_active": m.is_active,
        }

    async def rollback(self, name: str, target_version: int) -> dict | None:
        models = await self.repo.get_all(filters={"name": name})
        target = next((m for m in models if m.version == target_version), None)
        if not target:
            return None
        await self.repo.activate_version(target.id, name)
        return {"id": target.id, "version": target.version, "status": "active"}

"""Feature Registry Service."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import FeatureRepository
from app.services import BaseService


class FeatureService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = FeatureRepository(session)

    async def register_feature(
        self,
        name: str,
        display_name: str,
        feature_type: str,
        data_type: str,
        source_column: str | None = None,
        transformation: str | None = None,
        description: str | None = None,
    ) -> dict:
        existing = await self.repo.get_by_name(name)
        version = (existing.version + 1) if existing else 1
        feature = await self.repo.create(
            name=name,
            display_name=display_name,
            feature_type=feature_type,
            data_type=data_type,
            source_column=source_column,
            transformation=transformation,
            description=description,
            version=version,
        )
        return {"id": feature.id, "name": feature.name, "version": feature.version}

    async def get_active_features(self) -> list[dict]:
        features = await self.repo.get_active_features()
        return [
            {"id": f.id, "name": f.name, "display_name": f.display_name, "feature_type": f.feature_type, "importance_score": f.importance_score}
            for f in features
        ]

    async def get_top_features(self, limit: int = 10) -> list[dict]:
        features = await self.repo.get_top_features(limit)
        return [{"name": f.name, "importance_score": f.importance_score, "feature_type": f.feature_type} for f in features]

    async def update_importance(self, feature_id: str, score: float) -> None:
        await self.repo.update_by_id(feature_id, importance_score=score)

    async def deactivate_feature(self, feature_id: str) -> None:
        await self.repo.update_by_id(feature_id, is_active=False)

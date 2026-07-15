"""Graph Version Service - Knowledge graph version management."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import GraphVersionRepository
from app.services import BaseService


class GraphVersionService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.repo = GraphVersionRepository(session)

    async def create_version(
        self,
        node_count: int,
        relationship_count: int,
        source_dataset_id: str | None = None,
        build_duration_ms: float | None = None,
        snapshot_path: str | None = None,
        built_by: str = "system",
        activate: bool = True,
    ) -> dict:
        version_num = await self.repo.get_next_version_number()
        gv = await self.repo.create(
            version=version_num,
            status="building",
            node_count=node_count,
            relationship_count=relationship_count,
            source_dataset_id=source_dataset_id,
            build_duration_ms=build_duration_ms,
            snapshot_path=snapshot_path,
            built_by=built_by,
        )
        if activate:
            await self.repo.activate_version(gv.id)
        return {"id": gv.id, "version": version_num, "status": "active" if activate else "building"}

    async def get_active(self) -> dict | None:
        gv = await self.repo.get_active()
        if not gv:
            return None
        return {
            "id": gv.id, "version": gv.version, "node_count": gv.node_count,
            "relationship_count": gv.relationship_count, "tpke_mutations": gv.tpke_mutations,
            "status": gv.status, "created_at": str(gv.created_at),
        }

    async def increment_mutations(self, version_id: str, count: int = 1) -> None:
        gv = await self.repo.get_by_id(version_id)
        if gv:
            await self.repo.update_by_id(version_id, tpke_mutations=gv.tpke_mutations + count)

    async def list_versions(self, skip: int = 0, limit: int = 20) -> list[dict]:
        versions = await self.repo.get_all(skip=skip, limit=limit)
        return [
            {"id": v.id, "version": v.version, "status": v.status, "node_count": v.node_count, "is_active": v.is_active}
            for v in versions
        ]

"""
AMASCI Graph Versioning
==========================
Persistent graph version management with:
- PostgreSQL-backed version history (graph_versions table)
- Neo4j metadata node for active version tracking
- Snapshot support (export/restore)
- Rollback capability
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.graph.connection import Neo4jConnectionManager
from app.graph.utils import utc_now_iso
from app.repositories.domain import GraphVersionRepository

logger = logging.getLogger(__name__)

_VERSION_META_QUERY = """
    MERGE (meta:_GraphMeta {key: 'active_version'})
    SET meta.version = $version,
        meta.version_id = $version_id,
        meta.node_count = $node_count,
        meta.relationship_count = $relationship_count,
        meta.built_at = $built_at,
        meta.built_by = $built_by
    RETURN meta {.*} AS meta
"""

_GET_VERSION_META_QUERY = """
    MATCH (meta:_GraphMeta {key: 'active_version'})
    RETURN meta {.*} AS meta
"""


class GraphVersionManager:
    """
    Manages Knowledge Graph versions with dual persistence:
    - PostgreSQL: version history, metadata, audit trail
    - Neo4j: _GraphMeta node tracks active version in-graph

    Lifecycle:
    1. start_version() → creates pending version record
    2. complete_version() → marks active, updates Neo4j meta
    3. fail_version() → marks failed with error
    4. rollback() → reactivates a previous version
    """

    def __init__(self, connection: Neo4jConnectionManager, session: AsyncSession):
        self._conn = connection
        self._repo = GraphVersionRepository(session)
        self._settings = get_settings()

    async def start_version(
        self,
        source_dataset_id: str | None = None,
        built_by: str = "system",
    ) -> dict[str, Any]:
        """Create a new pending graph version."""
        version_num = await self._repo.get_next_version_number()
        gv = await self._repo.create(
            version=version_num,
            status="building",
            node_count=0,
            relationship_count=0,
            source_dataset_id=source_dataset_id,
            built_by=built_by,
        )
        logger.info(f"Started graph version {version_num} (id={gv.id})")
        return {"id": gv.id, "version": version_num, "status": "building"}

    async def complete_version(
        self,
        version_id: str,
        node_count: int,
        relationship_count: int,
        build_duration_ms: float,
        snapshot_path: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """Mark version as complete and activate it."""
        # Deactivate all previous, activate this one
        await self._repo.activate_version(version_id)

        # Update metrics
        gv = await self._repo.update_by_id(
            version_id,
            node_count=node_count,
            relationship_count=relationship_count,
            build_duration_ms=build_duration_ms,
            snapshot_path=snapshot_path,
            metadata_json=metadata,
        )

        # Update Neo4j meta node
        await self._update_neo4j_meta(
            version=gv.version,
            version_id=version_id,
            node_count=node_count,
            relationship_count=relationship_count,
            built_by=gv.built_by,
        )

        logger.info(f"Completed graph version {gv.version}: {node_count} nodes, {relationship_count} rels")
        return {
            "id": version_id,
            "version": gv.version,
            "status": "active",
            "node_count": node_count,
            "relationship_count": relationship_count,
        }

    async def fail_version(self, version_id: str, error: str) -> None:
        """Mark version as failed."""
        await self._repo.update_by_id(version_id, status="failed", metadata_json={"error": error})
        logger.error(f"Graph version {version_id} failed: {error}")

    async def get_active_version(self) -> dict[str, Any] | None:
        """Get the currently active graph version."""
        gv = await self._repo.get_active()
        if not gv:
            return None
        return {
            "id": gv.id,
            "version": gv.version,
            "status": gv.status,
            "node_count": gv.node_count,
            "relationship_count": gv.relationship_count,
            "tpke_mutations": gv.tpke_mutations,
            "build_duration_ms": gv.build_duration_ms,
            "created_at": str(gv.created_at),
        }

    async def get_neo4j_meta(self) -> dict[str, Any] | None:
        """Get the active version metadata from Neo4j."""
        records = await self._conn.execute_query(_GET_VERSION_META_QUERY)
        return records[0]["meta"] if records else None

    async def list_versions(self, skip: int = 0, limit: int = 20) -> list[dict[str, Any]]:
        """List all graph versions."""
        versions = await self._repo.get_all(skip=skip, limit=limit)
        return [
            {
                "id": v.id,
                "version": v.version,
                "status": v.status,
                "node_count": v.node_count,
                "relationship_count": v.relationship_count,
                "is_active": v.is_active,
                "build_duration_ms": v.build_duration_ms,
                "created_at": str(v.created_at),
            }
            for v in versions
        ]

    async def rollback(self, target_version: int) -> dict[str, Any] | None:
        """
        Rollback to a previous graph version.

        Note: This only updates the version metadata. Actual graph data
        rollback requires a snapshot restore (if snapshot_path exists).
        """
        versions = await self._repo.get_all(limit=100)
        target = next((v for v in versions if v.version == target_version), None)
        if not target:
            logger.error(f"Version {target_version} not found for rollback")
            return None

        if target.status == "failed":
            logger.error(f"Cannot rollback to failed version {target_version}")
            return None

        await self._repo.activate_version(target.id)

        # Update Neo4j meta
        await self._update_neo4j_meta(
            version=target.version,
            version_id=target.id,
            node_count=target.node_count,
            relationship_count=target.relationship_count,
            built_by="rollback",
        )

        logger.info(f"Rolled back to graph version {target_version}")
        return {"id": target.id, "version": target.version, "status": "active"}

    async def increment_tpke_mutations(self, count: int = 1) -> None:
        """Increment TPKE mutation counter on active version."""
        gv = await self._repo.get_active()
        if gv:
            await self._repo.update_by_id(gv.id, tpke_mutations=gv.tpke_mutations + count)

    async def save_snapshot(self, version_id: str, export_data: dict[str, Any]) -> str:
        """Save a graph snapshot to disk."""
        snapshot_dir = Path(self._settings.model_dir) / "graph_snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        gv = await self._repo.get_by_id(version_id)
        filename = f"graph_v{gv.version}_{int(time.time())}.json"
        filepath = snapshot_dir / filename

        with open(filepath, "w") as f:
            json.dump(export_data, f)

        await self._repo.update_by_id(version_id, snapshot_path=str(filepath))
        logger.info(f"Saved graph snapshot: {filepath}")
        return str(filepath)

    async def _update_neo4j_meta(
        self,
        version: int,
        version_id: str,
        node_count: int,
        relationship_count: int,
        built_by: str,
    ) -> None:
        """Update the _GraphMeta node in Neo4j."""
        try:
            await self._conn.execute_write(_VERSION_META_QUERY, {
                "version": version,
                "version_id": version_id,
                "node_count": node_count,
                "relationship_count": relationship_count,
                "built_at": utc_now_iso(),
                "built_by": built_by,
            })
        except Exception as e:
            logger.warning(f"Failed to update Neo4j meta node: {e}")

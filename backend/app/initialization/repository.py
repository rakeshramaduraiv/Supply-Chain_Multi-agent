"""
AMASCI Initialization Repository
===================================
Data access layer for system state and initialization logs.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.initialization import DatasetRecord, InitializationLog, SystemState

logger = logging.getLogger(__name__)

SYSTEM_STATE_ID = "system"


class SystemStateRepository:
    """Repository for the singleton SystemState record."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_state(self) -> SystemState | None:
        """Get the current system state."""
        result = await self._session.execute(
            select(SystemState).where(SystemState.id == SYSTEM_STATE_ID)
        )
        return result.scalar_one_or_none()

    async def ensure_state_exists(self) -> SystemState:
        """Create the system state record if it doesn't exist."""
        state = await self.get_state()
        if state is None:
            state = SystemState(id=SYSTEM_STATE_ID, is_initialized=False)
            self._session.add(state)
            await self._session.flush()
        return state

    async def mark_initialized(
        self,
        *,
        initialized_by: str = "system",
        dataset_filename: str,
        dataset_rows: int,
        dataset_columns: int,
        duration_ms: float,
        models_trained: int,
        graph_nodes: int,
        graph_relationships: int,
        metadata: dict | None = None,
    ) -> SystemState:
        """Mark the system as initialized."""
        state = await self.ensure_state_exists()
        state.is_initialized = True
        state.initialized_at = datetime.now(timezone.utc)
        state.initialized_by = initialized_by
        state.dataset_filename = dataset_filename
        state.dataset_rows = dataset_rows
        state.dataset_columns = dataset_columns
        state.initialization_duration_ms = duration_ms
        state.models_trained = models_trained
        state.graph_nodes = graph_nodes
        state.graph_relationships = graph_relationships
        state.metadata_json = metadata
        state.error_message = None
        await self._session.flush()
        return state

    async def mark_retrained(self, duration_ms: float) -> SystemState:
        """Update last retrain timestamp."""
        state = await self.ensure_state_exists()
        state.last_retrain_at = datetime.now(timezone.utc)
        await self._session.flush()
        return state

    async def mark_failed(self, error: str) -> SystemState:
        """Mark initialization as failed with error."""
        state = await self.ensure_state_exists()
        state.error_message = error
        await self._session.flush()
        return state

    async def is_initialized(self) -> bool:
        """Check if system is initialized."""
        state = await self.get_state()
        return state is not None and state.is_initialized


class InitializationLogRepository:
    """Repository for initialization audit logs."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def log_start(self, action: str, triggered_by: str, dataset_filename: str | None = None) -> InitializationLog:
        """Log the start of an initialization/retrain action."""
        entry = InitializationLog(
            action=action,
            status="started",
            triggered_by=triggered_by,
            dataset_filename=dataset_filename,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def log_step(self, log_id: str, step: str) -> None:
        """Update the current step."""
        await self._session.execute(
            update(InitializationLog)
            .where(InitializationLog.id == log_id)
            .values(step_completed=step)
        )
        await self._session.flush()

    async def log_complete(self, log_id: str, duration_ms: float, details: dict | None = None) -> None:
        """Mark log entry as completed."""
        await self._session.execute(
            update(InitializationLog)
            .where(InitializationLog.id == log_id)
            .values(status="completed", duration_ms=duration_ms, details_json=details)
        )
        await self._session.flush()

    async def log_failure(self, log_id: str, error: str, duration_ms: float) -> None:
        """Mark log entry as failed."""
        await self._session.execute(
            update(InitializationLog)
            .where(InitializationLog.id == log_id)
            .values(status="failed", error_message=error, duration_ms=duration_ms)
        )
        await self._session.flush()

    async def get_history(self, limit: int = 20) -> list[InitializationLog]:
        """Get recent initialization history."""
        result = await self._session.execute(
            select(InitializationLog)
            .order_by(InitializationLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class DatasetRecordRepository:
    """Repository for dataset records."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, **kwargs) -> DatasetRecord:
        """Create a new dataset record."""
        record = DatasetRecord(**kwargs)
        self._session.add(record)
        await self._session.flush()
        return record

    async def update_status(self, record_id: str, status: str, **kwargs) -> None:
        """Update dataset record status."""
        values = {"status": status, **kwargs}
        await self._session.execute(
            update(DatasetRecord).where(DatasetRecord.id == record_id).values(**values)
        )
        await self._session.flush()

    async def get_by_type(self, dataset_type: str) -> list[DatasetRecord]:
        """Get all records of a given type."""
        result = await self._session.execute(
            select(DatasetRecord)
            .where(DatasetRecord.dataset_type == dataset_type)
            .order_by(DatasetRecord.created_at.desc())
        )
        return list(result.scalars().all())

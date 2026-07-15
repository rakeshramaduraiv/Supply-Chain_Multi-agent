"""
AMASCI Initialization Startup Handler
=========================================
Integrates with FastAPI lifespan to check system state on boot.

On first startup:
- Detects if system is uninitialized
- Checks for master dataset in data/raw/
- Runs full initialization pipeline
- Marks system as initialized in PostgreSQL

On subsequent startups:
- Verifies system is initialized
- Logs status
- Does NOT retrain
"""

import logging
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.postgres import async_session_factory
from app.initialization.repository import (
    DatasetRecordRepository,
    InitializationLogRepository,
    SystemStateRepository,
)
from app.initialization.service import InitializationService

logger = logging.getLogger(__name__)
settings = get_settings()

# File-based lock to prevent re-initialization without DB
_INIT_LOCK_FILE = Path(settings.model_dir) / ".initialized"


def is_initialized_on_disk() -> bool:
    """Quick check via filesystem (no DB required)."""
    return _INIT_LOCK_FILE.exists()


def mark_initialized_on_disk(metadata: dict) -> None:
    """Write initialization marker to disk."""
    import json
    _INIT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INIT_LOCK_FILE.write_text(json.dumps(metadata, indent=2, default=str))


async def check_and_initialize() -> None:
    """
    Main startup initialization check.
    Called from FastAPI lifespan after DB connections are established.
    """
    # Quick filesystem check first (avoids DB query on every restart)
    if is_initialized_on_disk():
        logger.info("System already initialized (disk marker found)")
        return

    # Check database state
    async with async_session_factory() as session:
        try:
            repo = SystemStateRepository(session)
            state = await repo.ensure_state_exists()
            await session.commit()

            if state.is_initialized:
                logger.info("System already initialized (DB state confirmed)")
                # Sync disk marker
                mark_initialized_on_disk({"initialized_at": str(state.initialized_at)})
                return

        except Exception as e:
            logger.warning(f"Could not check DB state (tables may not exist yet): {e}")
            # If tables don't exist, check disk marker only
            if is_initialized_on_disk():
                return

    # System is NOT initialized — attempt auto-initialization
    logger.info("System not initialized. Checking for master dataset...")

    init_service = InitializationService()
    dataset_path = init_service.find_master_dataset()

    if dataset_path is None:
        logger.info(
            "No master dataset found in data/raw/. "
            "Place DataCoSupplyChainDataset.csv in backend/data/raw/ and restart."
        )
        return

    logger.info(f"Master dataset found: {dataset_path.name}")
    logger.info("Starting automatic system initialization...")

    # Execute initialization
    start_time = time.perf_counter()
    result = init_service.execute(dataset_path)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if result["status"] == "completed":
        # Persist to database
        async with async_session_factory() as session:
            try:
                state_repo = SystemStateRepository(session)
                log_repo = InitializationLogRepository(session)
                dataset_repo = DatasetRecordRepository(session)

                # Log the initialization
                log_entry = await log_repo.log_start(
                    action="initialize",
                    triggered_by="system_startup",
                    dataset_filename=result.get("dataset_filename"),
                )
                await log_repo.log_complete(
                    log_id=log_entry.id,
                    duration_ms=duration_ms,
                    details=result.get("steps"),
                )

                # Mark system as initialized
                await state_repo.mark_initialized(
                    initialized_by="system_startup",
                    dataset_filename=result.get("dataset_filename", ""),
                    dataset_rows=result.get("dataset_rows", 0),
                    dataset_columns=result.get("dataset_columns", 0),
                    duration_ms=duration_ms,
                    models_trained=result.get("models_trained", 0),
                    graph_nodes=result.get("graph_nodes", 0),
                    graph_relationships=result.get("graph_relationships", 0),
                    metadata=result.get("steps"),
                )

                # Record the dataset
                await dataset_repo.create(
                    filename=result.get("dataset_filename", ""),
                    file_path=str(dataset_path),
                    dataset_type="master",
                    row_count=result.get("dataset_rows", 0),
                    column_count=result.get("dataset_columns", 0),
                    file_size_bytes=dataset_path.stat().st_size,
                    status="processed",
                    quality_score=result.get("steps", {}).get("data_engineering", {}).get("quality_score"),
                    processing_duration_ms=duration_ms,
                )

                await session.commit()
                logger.info("Initialization state persisted to database")

            except Exception as e:
                logger.error(f"Failed to persist initialization state: {e}")
                await session.rollback()

        # Write disk marker
        mark_initialized_on_disk({
            "status": "completed",
            "dataset": result.get("dataset_filename"),
            "duration_ms": duration_ms,
            "models_trained": result.get("models_trained"),
        })

        logger.info(f"=== SYSTEM READY (initialized in {duration_ms / 1000:.1f}s) ===")

    elif result["status"] == "failed":
        logger.error(f"System initialization FAILED: {result.get('error')}")

        # Log failure to DB
        async with async_session_factory() as session:
            try:
                state_repo = SystemStateRepository(session)
                log_repo = InitializationLogRepository(session)

                await state_repo.mark_failed(result.get("error", "Unknown error"))

                log_entry = await log_repo.log_start(
                    action="initialize",
                    triggered_by="system_startup",
                    dataset_filename=result.get("dataset_filename"),
                )
                await log_repo.log_failure(
                    log_id=log_entry.id,
                    error=result.get("error", "Unknown"),
                    duration_ms=duration_ms,
                )
                await session.commit()
            except Exception:
                await session.rollback()

    else:
        logger.info(f"Initialization skipped: {result.get('reason', 'unknown')}")

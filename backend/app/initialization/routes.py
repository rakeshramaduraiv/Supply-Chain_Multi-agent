"""
AMASCI Initialization API Routes
====================================
Admin-only endpoints for system initialization management.
"""

import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.postgres import get_db_session
from app.initialization.repository import (
    DatasetRecordRepository,
    InitializationLogRepository,
    SystemStateRepository,
)
from app.initialization.service import InitializationService
from app.initialization.startup import is_initialized_on_disk, mark_initialized_on_disk

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/admin/initialization", tags=["Administration"])


@router.get("/status")
async def get_initialization_status(session: AsyncSession = Depends(get_db_session)):
    """Get current system initialization status."""
    repo = SystemStateRepository(session)
    try:
        state = await repo.get_state()
    except Exception:
        return {
            "is_initialized": is_initialized_on_disk(),
            "source": "disk",
            "initialized_at": None,
            "initialized_by": None,
            "dataset_filename": None,
            "dataset_rows": None,
            "models_trained": None,
            "graph_nodes": None,
            "graph_relationships": None,
            "initialization_duration_ms": None,
            "last_retrain_at": None,
            "error_message": None,
        }

    if state is None:
        return {
            "is_initialized": is_initialized_on_disk(),
            "source": "disk",
        }

    return {
        "is_initialized": state.is_initialized,
        "initialized_at": state.initialized_at,
        "initialized_by": state.initialized_by,
        "dataset_filename": state.dataset_filename,
        "dataset_rows": state.dataset_rows,
        "models_trained": state.models_trained,
        "graph_nodes": state.graph_nodes,
        "graph_relationships": state.graph_relationships,
        "initialization_duration_ms": state.initialization_duration_ms,
        "last_retrain_at": state.last_retrain_at,
        "error_message": state.error_message,
    }


@router.get("/history")
async def get_initialization_history(session: AsyncSession = Depends(get_db_session)):
    """Get initialization and retraining history."""
    repo = InitializationLogRepository(session)
    logs = await repo.get_history(limit=20)
    return [
        {
            "id": log.id,
            "action": log.action,
            "status": log.status,
            "triggered_by": log.triggered_by,
            "dataset_filename": log.dataset_filename,
            "duration_ms": log.duration_ms,
            "step_completed": log.step_completed,
            "error_message": log.error_message,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.post("/retrain")
async def trigger_retrain(session: AsyncSession = Depends(get_db_session)):
    """
    Administrator-triggered retraining.
    Uses the existing processed master dataset.
    """
    state_repo = SystemStateRepository(session)
    state = await state_repo.get_state()

    if state is None or not state.is_initialized:
        raise HTTPException(status_code=400, detail="System not initialized. Cannot retrain.")

    log_repo = InitializationLogRepository(session)
    log_entry = await log_repo.log_start(
        action="retrain",
        triggered_by="admin_api",
        dataset_filename=state.dataset_filename,
    )
    await session.commit()

    start_time = time.perf_counter()

    try:
        # Load processed dataset
        processed_path = Path(settings.upload_dir) / "processed_master.parquet"
        if not processed_path.exists():
            raise FileNotFoundError("Processed master dataset not found. Re-initialize the system.")

        import pandas as pd
        df = pd.read_parquet(processed_path)

        # Retrain all models
        from app.ml.training import TrainingOrchestrator
        orchestrator = TrainingOrchestrator()
        results = orchestrator.train_all(df, dataset_version="retrain")

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Update state
        await state_repo.mark_retrained(duration_ms)
        await log_repo.log_complete(
            log_id=log_entry.id,
            duration_ms=duration_ms,
            details={k: v.to_dict() for k, v in results.items()},
        )
        await session.commit()

        return {
            "status": "completed",
            "models_retrained": len(results),
            "duration_ms": round(duration_ms, 1),
            "models": {
                k: {"version": v.version_id, "accuracy": v.metrics.get("accuracy", 0)}
                for k, v in results.items()
            },
        }

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        await log_repo.log_failure(log_id=log_entry.id, error=str(e), duration_ms=duration_ms)
        await session.commit()
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")


@router.post("/initialize")
async def trigger_manual_initialization(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Administrator-triggered manual initialization with uploaded dataset.
    Only works if system is NOT already initialized.
    """
    state_repo = SystemStateRepository(session)
    if await state_repo.is_initialized():
        raise HTTPException(
            status_code=400,
            detail="System already initialized. Use /retrain to update models.",
        )

    # Save uploaded file
    raw_dir = Path("./data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = raw_dir / file.filename

    content = await file.read()
    dataset_path.write_bytes(content)

    # Run initialization
    init_service = InitializationService()
    start_time = time.perf_counter()
    result = init_service.execute(dataset_path)
    duration_ms = (time.perf_counter() - start_time) * 1000

    if result["status"] == "completed":
        log_repo = InitializationLogRepository(session)
        dataset_repo = DatasetRecordRepository(session)

        log_entry = await log_repo.log_start(
            action="initialize",
            triggered_by="admin_api",
            dataset_filename=file.filename,
        )
        await log_repo.log_complete(log_id=log_entry.id, duration_ms=duration_ms, details=result.get("steps"))

        await state_repo.mark_initialized(
            initialized_by="admin_api",
            dataset_filename=file.filename or "",
            dataset_rows=result.get("dataset_rows", 0),
            dataset_columns=result.get("dataset_columns", 0),
            duration_ms=duration_ms,
            models_trained=result.get("models_trained", 0),
            graph_nodes=result.get("graph_nodes", 0),
            graph_relationships=result.get("graph_relationships", 0),
            metadata=result.get("steps"),
        )

        await dataset_repo.create(
            filename=file.filename or "",
            file_path=str(dataset_path),
            dataset_type="master",
            row_count=result.get("dataset_rows", 0),
            column_count=result.get("dataset_columns", 0),
            file_size_bytes=len(content),
            status="processed",
            processing_duration_ms=duration_ms,
        )

        await session.commit()
        mark_initialized_on_disk({"status": "completed", "dataset": file.filename})

        return {"status": "completed", **result}

    raise HTTPException(status_code=500, detail=f"Initialization failed: {result.get('error')}")

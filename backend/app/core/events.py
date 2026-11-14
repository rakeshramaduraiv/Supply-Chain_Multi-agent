"""
AMASCI Application Events
===========================
Startup and shutdown lifecycle management.
"""

import logging
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def on_startup() -> None:
    """Application startup tasks."""
    logger.info("AMASCI Platform starting up...")

    # Defect 4b: assert holdout guard is coherent before serving any request
    if settings.use_real_holdout_actuals and settings.holdout_start_date is None:
        raise RuntimeError(
            "Configuration error: use_real_holdout_actuals=True but "
            "holdout_start_date is None. Both must be set together. "
            "Set HOLDOUT_START_DATE in your .env file."
        )
    logger.info(
        "Holdout guard: use_real_holdout_actuals=%s holdout_start_date=%s",
        settings.use_real_holdout_actuals, settings.holdout_start_date,
    )

    # Ensure data directories exist
    for dir_path in [settings.upload_dir, settings.model_dir, settings.log_dir, "./data/raw"]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")

    # Part B: reset cycle on startup so demo always starts from Period 1 of 4.
    # NEVER touches base.parquet, registry.json, or model artifacts.
    # Disable with RESET_CYCLE_ON_STARTUP=false in .env.
    if settings.reset_cycle_on_startup:
        await _reset_cycle_on_startup()

    # System initialization check
    try:
        from app.initialization.startup import check_and_initialize
        await check_and_initialize()
    except Exception as e:
        logger.error(f"Initialization check failed: {e}", exc_info=True)
        # Non-fatal: system can still serve health checks

    logger.info("Startup complete.")


async def _reset_cycle_on_startup() -> None:
    """
    Wipe cycle_state.json and all uploaded increment parquets.
    Assert base.parquet checksum is unchanged before and after.
    Never deletes base.parquet, registry.json, or any model artifact.
    """
    import hashlib
    from app.services.cycle_state_store import reset_all as _reset_state
    from app.store.cumulative import CumulativeStore
    from app.api.v1.endpoints.dataset_summary import clear_dataset_cache, clear_forecast_cache

    # Locate base.parquet for checksum guard
    base_path = Path(settings.model_dir).parent / "cumulative" / "base.parquet"
    if not base_path.exists():
        base_path = Path("data/cumulative/base.parquet")

    checksum_before: str | None = None
    if base_path.exists():
        checksum_before = hashlib.sha256(base_path.read_bytes()).hexdigest()

    # 1. Clear cycle_state.json
    try:
        _reset_state()
        logger.info("[startup_reset] cycle_state.json cleared")
    except Exception as e:
        logger.warning("[startup_reset] cycle_state clear failed (non-fatal): %s", e)

    # 2. Reset increment parquets (base.parquet untouched by CumulativeStore.reset_increments)
    increments_deleted = 0
    try:
        store = CumulativeStore()
        result = store.reset_increments(confirm=True)
        increments_deleted = result.get("deleted", 0) if isinstance(result, dict) else 0
        logger.info("[startup_reset] %d increment(s) deleted", increments_deleted)
    except Exception as e:
        logger.warning("[startup_reset] increment reset failed (non-fatal): %s", e)

    # 3. Clear caches
    try:
        clear_dataset_cache()
        clear_forecast_cache()
    except Exception as e:
        logger.warning("[startup_reset] cache clear failed (non-fatal): %s", e)

    # 4. Assert base.parquet checksum unchanged
    if checksum_before is not None and base_path.exists():
        checksum_after = hashlib.sha256(base_path.read_bytes()).hexdigest()
        if checksum_after != checksum_before:
            raise RuntimeError(
                f"[startup_reset] INVARIANT VIOLATED: base.parquet checksum changed "
                f"during startup reset! before={checksum_before[:12]}… "
                f"after={checksum_after[:12]}… "
                f"This must never happen — base.parquet is training data."
            )
        logger.info("[startup_reset] base.parquet checksum verified unchanged (%s…)", checksum_before[:12])
    else:
        logger.info("[startup_reset] base.parquet not found — skipping checksum check")

    logger.info(
        "[startup_reset] Cycle reset complete: increments_deleted=%d, "
        "base.parquet_untouched=True. Set RESET_CYCLE_ON_STARTUP=false to disable.",
        increments_deleted,
    )


async def on_shutdown() -> None:
    """Application shutdown tasks."""
    logger.info("AMASCI Platform shutting down...")
    logger.info("Shutdown complete.")

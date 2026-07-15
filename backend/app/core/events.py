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

    # Ensure data directories exist
    for dir_path in [settings.upload_dir, settings.model_dir, settings.log_dir, "./data/raw"]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Debug mode: {settings.debug}")

    # System initialization check
    try:
        from app.initialization.startup import check_and_initialize
        await check_and_initialize()
    except Exception as e:
        logger.error(f"Initialization check failed: {e}", exc_info=True)
        # Non-fatal: system can still serve health checks

    logger.info("Startup complete.")


async def on_shutdown() -> None:
    """Application shutdown tasks."""
    logger.info("AMASCI Platform shutting down...")
    logger.info("Shutdown complete.")

"""
AMASCI System Initialization Module
=======================================
Handles one-time system setup and administrator-triggered retraining.

Architecture:
- service.py: Core initialization pipeline orchestrator
- startup.py: FastAPI lifespan integration (auto-init on first boot)
- repository.py: Database persistence for system state
- routes.py: Admin API endpoints for manual retrain/status

Flow:
1. Backend starts → check_and_initialize() called
2. If not initialized AND dataset exists in data/raw/ → run full pipeline
3. Mark system as initialized (DB + disk)
4. Never auto-retrain again
"""

from app.initialization.service import InitializationService
from app.initialization.startup import check_and_initialize, is_initialized_on_disk

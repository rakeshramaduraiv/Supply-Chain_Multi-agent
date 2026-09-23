"""
app/api/v1/endpoints/cycle_routes.py
=====================================
Backend-authoritative lifecycle endpoints.

GET  /cycle/state              — full lifecycle state (UI source of truth)
POST /cycle/forecast/{period}  — issue Stage 0 forecast for a period
POST /cycle/reset              — wipe cycle state + increments (demo reset)
GET  /cycle/{cycle_id}/stages  — resync missed WebSocket events
GET  /cycle/status             — legacy footer summary
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.cycle_store import get_events, get_latest_cycle_summary
from app.services.cycle_state_store import (
    get_cycle_state_response,
    record_stage,
    reset_all as _reset_state,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cycle", tags=["Cycle"])


# ── GET /cycle/state ──────────────────────────────────────────────────────────

@router.get("/state", response_model=dict[str, Any])
async def get_cycle_state():
    """
    Single source of truth for the forecast lifecycle.

    Returns current_period, next_expected_period, trained_through,
    available_periods (each with stage_statuses, can_upload, locked_reason).

    The UI derives ALL lifecycle state from this endpoint.
    No localStorage lifecycle values. No browser counter.
    """
    return get_cycle_state_response()


# ── POST /cycle/forecast/{period} ─────────────────────────────────────────────

@router.post("/forecast/{period}", response_model=dict[str, Any])
async def issue_forecast(period: str):
    """
    Stage 0: Generate and persist a forecast for *period*.

    This is the first action in every cycle. It must be called before
    actuals can be uploaded for that period.

    Returns the forecast result and records Stage 0 in cycle state.
    Raises 409 if a forecast for this period already exists.
    Raises 409 if this period is not the next expected period.
    """
    from app.services.cycle_state_store import (
        get_period_state, get_cycle_state_response as _state,
    )
    from app.api.v1.endpoints.dataset_summary import _compute_auto_forecast

    # Ordering guard: only allow the next expected period
    state = _state()
    next_expected = state.get("next_expected_period")
    if next_expected and period != next_expected:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "period_out_of_order",
                "submitted": period,
                "expected": next_expected,
                "message": (
                    f"Cannot issue forecast for {period!r}: "
                    f"next expected period is {next_expected!r}. "
                    f"Complete {next_expected!r} first."
                ),
            },
        )

    # Idempotency: if Stage 0 already completed for this period, return existing
    ps = get_period_state(period)
    if ps and ps.get("stage_statuses", {}).get("0", {}).get("status") == "COMPLETED":
        return {
            "already_issued": True,
            "period": period,
            "stage_status": ps["stage_statuses"]["0"],
        }

    t0 = time.perf_counter()
    try:
        forecast = _compute_auto_forecast(target_period=period)
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000
        record_stage(
            period=period, stage=0,
            status="FAILED", duration_ms=duration_ms,
            detail={}, error=str(e),
        )
        raise HTTPException(500, f"Forecast generation failed: {e}")

    duration_ms = (time.perf_counter() - t0) * 1000

    if not forecast.get("ready"):
        record_stage(
            period=period, stage=0,
            status="FAILED", duration_ms=duration_ms,
            detail={"message": forecast.get("message", "")},
            error=forecast.get("message"),
        )
        raise HTTPException(
            422,
            f"Forecast not ready: {forecast.get('message', 'unknown reason')}",
        )

    record_stage(
        period=period, stage=0,
        status="COMPLETED", duration_ms=duration_ms,
        detail={
            "target_period":   forecast.get("target_period", period),
            "template_period": forecast.get("template_period", ""),
            "trained_through": forecast.get("trained_through", ""),
            "total_forecasts": forecast.get("total_forecasts", 0),
            "overall_confidence": forecast.get("overall_confidence", 0),
        },
    )

    return {
        "already_issued": False,
        "period": period,
        "forecast": forecast,
        "duration_ms": round(duration_ms, 1),
    }


# ── POST /cycle/reset ─────────────────────────────────────────────────────────

@router.post("/reset", response_model=dict[str, Any])
async def reset_cycle(confirm: bool = False):
    """
    Reset the full lifecycle for a clean demo run.

    Clears:
      - cycle_state.json (all period stage records)
      - forecast_runs table rows (via CumulativeStore reset)
      - TPKE inferred edges in Neo4j
      - All uploaded increment parquets (cumulative store returns to base)

    NEVER touches:
      - base.parquet (training data)
      - model registry / trained .joblib files

    Requires ?confirm=true. Reports base.parquet checksum before and after
    to prove it was not modified.
    """
    if not confirm:
        raise HTTPException(
            400,
            "Pass ?confirm=true to reset the cycle. "
            "This deletes all cycle state and uploaded increments. "
            "base.parquet and trained models are never touched.",
        )

    from app.store.cumulative import CumulativeStore
    from app.api.v1.endpoints.dataset_summary import clear_dataset_cache

    settings_path = None
    base_checksum_before = None
    base_checksum_after = None

    # Compute base.parquet checksum before
    try:
        from app.core.config import get_settings
        _s = get_settings()
        base_path = Path(_s.upload_dir) / "base.parquet"
        if not base_path.exists():
            # Try cumulative store path
            base_path = Path("data/cumulative/base.parquet")
        if base_path.exists():
            h = hashlib.sha256(base_path.read_bytes()).hexdigest()
            base_checksum_before = h
            settings_path = str(base_path)
    except Exception as e:
        logger.warning(f"[Reset] base checksum before failed: {e}")

    errors = []

    # 1. Clear cycle state
    try:
        _reset_state()
    except Exception as e:
        errors.append(f"cycle_state: {e}")

    # 2. Reset cumulative store increments (base.parquet untouched)
    increment_result = {}
    try:
        store = CumulativeStore()
        increment_result = store.reset_increments(confirm=True)
        clear_dataset_cache()
    except Exception as e:
        errors.append(f"increments: {e}")

    # 3. Clear TPKE inferred edges
    tpke_cleared = 0
    try:
        from app.graph.connection import get_connection_manager
        conn = get_connection_manager()
        result = await conn.execute_query(
            "MATCH ()-[r:TPKE_INFERRED]->() DELETE r RETURN count(r) AS deleted"
        )
        tpke_cleared = result[0]["deleted"] if result else 0
    except Exception as e:
        logger.warning(f"[Reset] TPKE clear failed (non-fatal): {e}")
        errors.append(f"tpke_edges: {e}")

    # Compute base.parquet checksum after — must match
    try:
        if base_path and base_path.exists():
            h2 = hashlib.sha256(base_path.read_bytes()).hexdigest()
            base_checksum_after = h2
    except Exception as e:
        logger.warning(f"[Reset] base checksum after failed: {e}")

    checksum_ok = (
        base_checksum_before is not None
        and base_checksum_after is not None
        and base_checksum_before == base_checksum_after
    )

    return {
        "status": "ok" if not errors else "partial",
        "cycle_state_cleared": True,
        "increments_reset": increment_result,
        "tpke_edges_cleared": tpke_cleared,
        "base_parquet_path": settings_path,
        "base_checksum_before": base_checksum_before,
        "base_checksum_after": base_checksum_after,
        "base_unchanged": checksum_ok,
        "errors": errors,
    }


# ── GET /cycle/status (legacy footer) ────────────────────────────────────────

@router.get("/status", response_model=dict[str, Any])
async def get_cycle_status():
    """
    Return persistent cycle status for the footer.
    All fields are None when no cycle has run yet.
    """
    summary = get_latest_cycle_summary()
    return summary or {}


# ── GET /cycle/{cycle_id}/stages (WebSocket resync) ──────────────────────────

@router.get("/{cycle_id}/stages", response_model=list[dict[str, Any]])
async def get_cycle_stages(cycle_id: str):
    """
    Return all stage events recorded for *cycle_id*.
    404 if the cycle_id is unknown or evicted from the in-process store.
    """
    events = get_events(cycle_id)
    if events is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"cycle_id {cycle_id!r} not found. "
                "It may have been evicted (only the last 20 cycles are kept)."
            ),
        )
    return events

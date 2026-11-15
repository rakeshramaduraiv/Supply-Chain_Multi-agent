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


# ── GET /cycle/preflight ──────────────────────────────────────────────────────

@router.get("/preflight", response_model=dict[str, Any])
async def cycle_preflight():
    """
    System-readiness check for the forecast cycle.
    Returns pass/fail for each prerequisite with a specific remedy string.
    Overall ready=true only when ALL blocking checks pass.
    """
    import json
    import pandas as pd
    from app.core.config import get_settings
    from app.core.data_files import assert_real_file, resolve_actuals_dir, MANIFEST_REQUIRED_COLS

    checks: list[dict] = []
    blocking: list[str] = []

    def _check(name: str, passed: bool, detail: str, remedy: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail, "remedy": remedy})
        if not passed:
            blocking.append(f"{name}: {detail}")

    settings = get_settings()

    # 1. Raw dataset
    try:
        raw_csv = Path(settings.raw_data_dir) / "DataCoSupplyChainDataset.csv"
        assert_real_file(raw_csv)
        size_mb = round(raw_csv.stat().st_size / 1_048_576, 1)
        _check("raw_dataset", True, f"{raw_csv.name} present ({size_mb} MB)", "Already present")
    except (FileNotFoundError, RuntimeError) as e:
        _check("raw_dataset", False, str(e),
               "Download DataCoSupplyChainDataset.csv and place in backend/data/raw/")

    # 2. Holdout manifest
    actuals_dir = resolve_actuals_dir()
    manifest_path = actuals_dir / "holdout_manifest.csv"
    try:
        assert_real_file(manifest_path)
        df_m = pd.read_csv(manifest_path)
        missing_cols = MANIFEST_REQUIRED_COLS - set(df_m.columns)
        if missing_cols:
            raise RuntimeError(f"Missing columns: {sorted(missing_cols)}")
        _check("holdout_manifest", True,
               f"{manifest_path.name} present, {len(df_m)} rows, columns OK", "Already present")
    except (FileNotFoundError, RuntimeError) as e:
        _check("holdout_manifest", False, str(e),
               "Run: make bootstrap  (or python scripts/create_holdout_actuals.py)")

    # 3. Actuals files
    actuals_found = []
    actuals_lfs = []
    if actuals_dir.exists():
        for fname in sorted(actuals_dir.glob("????_??_actual.csv")):
            try:
                assert_real_file(fname)
                actuals_found.append(fname.stem.replace("_actual", "").replace("_", "-"))
            except RuntimeError:
                actuals_lfs.append(fname.name)
    if actuals_lfs:
        _check("actuals_files", False, f"{len(actuals_lfs)} LFS pointer(s): {actuals_lfs}",
               "Run: git lfs install && git lfs pull")
    elif not actuals_found:
        _check("actuals_files", False, f"No actuals CSVs found in {actuals_dir}",
               "Run: make bootstrap  (or python scripts/create_holdout_actuals.py)")
    else:
        _check("actuals_files", True, f"{len(actuals_found)} files: {actuals_found}", "Already present")

    # 4. processed_master.parquet
    try:
        pq_path = Path(settings.upload_dir) / "processed_master.parquet"
        assert_real_file(pq_path)
        df_pq = pd.read_parquet(pq_path)
        max_date = str(df_pq["order_date"].max())[:10] if "order_date" in df_pq.columns else "unknown"
        _check("processed_parquet", True,
               f"processed_master.parquet: {len(df_pq):,} rows, max_date={max_date}", "Already present")
    except (FileNotFoundError, RuntimeError, Exception) as e:
        _check("processed_parquet", False, str(e),
               "Run: make bootstrap  (POST /api/v1/initialization/run)")

    # 5. Model registry
    try:
        registry_path = Path(settings.model_dir) / "registry.json"
        assert_real_file(registry_path)
        reg_data = json.loads(registry_path.read_text())
        active = [v for v in reg_data.get("versions", []) if v.get("status") == "active"]
        _check("model_registry", True, f"registry.json: {len(active)} active model(s)", "Already present")
    except (FileNotFoundError, RuntimeError) as e:
        _check("model_registry", False, str(e),
               "Run: make bootstrap  (POST /api/v1/initialization/run)")
    except Exception as e:
        _check("model_registry", False, f"registry.json unreadable: {e}", "Run: make bootstrap")

    # 6. Models on disk
    try:
        from app.ml.registry import ModelRegistry
        from app.ml.utils import IntelligenceType
        reg = ModelRegistry()
        missing_models = []
        for it in [IntelligenceType.DEMAND, IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS]:
            v = reg.get_latest_version(it)
            if not v:
                missing_models.append(it.value)
                continue
            mp = Path(getattr(v, "model_path", "") or "")
            if not mp.exists():
                missing_models.append(f"{it.value} ({mp.name})")
        if missing_models:
            _check("models_on_disk", False, f"Missing model files: {missing_models}",
                   "Run: make bootstrap  (POST /api/v1/initialization/run)")
        else:
            _check("models_on_disk", True, "All 3 agent models present", "Already present")
    except Exception as e:
        _check("models_on_disk", False, f"Registry read failed: {e}", "Run: make bootstrap")

    # 7. Neo4j
    try:
        from app.graph.connection import get_connection_manager
        conn = get_connection_manager()
        result = await conn.execute_query("MATCH (n) RETURN count(n) AS nodes LIMIT 1")
        nodes = result[0]["nodes"] if result else 0
        _check("neo4j", True, f"Reachable, {nodes:,} nodes", "Already connected")
    except Exception as e:
        _check("neo4j", False, f"Unreachable: {e}",
               "Start Neo4j: docker-compose up neo4j  or  neo4j start")

    # 8. cycle_state.json
    try:
        from app.services.cycle_state_store import _load_raw
        raw = _load_raw()
        n_periods = len(raw.get("periods", {}))
        _check("cycle_state", True,
               f"cycle_state.json readable, {n_periods} period(s) recorded", "Already present")
    except Exception as e:
        _check("cycle_state", False, f"cycle_state.json unreadable: {e}",
               "Delete backend/data/cycle_state.json and restart")

    ready = len(blocking) == 0
    return {
        "ready": ready,
        "checks": checks,
        "blocking_issues": blocking,
        "summary": f"{sum(c['passed'] for c in checks)}/{len(checks)} checks passed",
    }


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
        msg = forecast.get("message", "unknown reason")
        # Distinguish system-not-initialized from a transient forecast error
        not_init_keywords = ("no model", "registry", "not found", "parquet", "not initialized")
        reason_code = "NOT_INITIALIZED" if any(k in msg.lower() for k in not_init_keywords) else "FORECAST_ERROR"
        record_stage(
            period=period, stage=0,
            status="FAILED", duration_ms=duration_ms,
            detail={"message": msg, "reason": reason_code},
            error=msg,
        )
        raise HTTPException(
            422,
            {
                "reason": reason_code,
                "message": msg,
                "remedy": "Run system initialization: make bootstrap  or  POST /api/v1/initialization/run"
                if reason_code == "NOT_INITIALIZED" else msg,
            },
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
        # Also clear the auto-forecast cache so next call recomputes from scratch
        from app.api.v1.endpoints.dataset_summary import clear_forecast_cache
        clear_forecast_cache()
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


# ── POST /cycle/advance/{period} ──────────────────────────────────────────────

@router.post("/advance/{period}", response_model=dict[str, Any])
async def advance_cycle(period: str):
    """
    Mark all stages (0-6) as COMPLETED for *period* and record Stage 0
    for the next period. No guards, no DB, no Neo4j required.

    This is the lightweight "UI cycle complete" endpoint used when the
    frontend has done client-side validation and just needs the backend
    to advance next_expected_period to the next month.

    Idempotent: calling it twice for the same period is safe.
    """
    import pandas as pd

    # Compute next period via pandas Period arithmetic (same as period.py)
    try:
        next_p = str(pd.Period(period, freq="M") + 1)
    except Exception:
        raise HTTPException(400, f"Invalid period format: {period!r}. Expected YYYY-MM.")

    t = time.perf_counter()
    dur = 1.0

    # Record stages 0-6 as COMPLETED for this period
    for stage in range(7):
        record_stage(
            period=period,
            stage=stage,
            status="COMPLETED",
            duration_ms=dur,
            detail={"source": "ui_advance", "period": period},
        )

    # Record Stage 0 for the next period (= forecast issued for next cycle)
    record_stage(
        period=next_p,
        stage=0,
        status="COMPLETED",
        duration_ms=dur,
        detail={"source": "ui_advance", "carried_from": period},
    )

    return {
        "period_completed": period,
        "next_period": next_p,
        "stages_recorded": list(range(7)),
        "duration_ms": round((time.perf_counter() - t) * 1000, 1),
    }


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

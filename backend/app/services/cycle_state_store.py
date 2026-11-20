"""
app/services/cycle_state_store.py
===================================
File-backed, backend-authoritative state machine for the forecast lifecycle.

Step model (1-7 + close):
  1  Generate Forecast
  2  Upload Actuals
  3  Actual vs Predicted
  4  Knowledge Graph Update   ← must come BEFORE RCA
  5  Root Cause Analysis      ← traverses the updated graph
  6  TPKE Evolution
  7  Learn & Agent Scores
  8  (close_period) → advances next_expected_period

current_step(ps) returns 1..7 while steps are pending, 8 when 1-7 are all COMPLETED.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.core.data_files import assert_real_file, resolve_actuals_dir, MANIFEST_REQUIRED_COLS

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()

STEP_NAMES = {
    1: "Generate Forecast",
    2: "Upload Actuals",
    3: "Actual vs Predicted",
    4: "Knowledge Graph Update",
    5: "Root Cause Analysis",
    6: "TPKE Evolution",
    7: "Learn & Agent Scores",
}

# A RUNNING step that is older than this is treated as FAILED (process killed).
_RUNNING_TIMEOUT_SECS = 600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path() -> Path:
    settings = get_settings()
    return Path(settings.model_dir).parent / "cycle_state.json"


def _load_raw() -> dict:
    path = _state_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # One-time migration: old file used stage_statuses → treat as empty
            if "periods" not in data and "stage_statuses" in str(data):
                logger.warning("[CycleState] Old stage-based state detected — resetting to empty step model")
                return {"periods": {}}
            return data
        except Exception as e:
            logger.warning(f"[CycleState] load failed: {e}")
    return {"periods": {}}


def _save_raw(data: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, default=str)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _period_record(data: dict, period: str) -> dict:
    return data.setdefault("periods", {}).setdefault(period, {
        "period": period,
        "steps": {},
        "closed_at": None,
        "updated_at": None,
    })


# ── Step status helpers ───────────────────────────────────────────────────────

def step_status(ps: dict, step: int) -> str:
    """Return the status string for a step, accounting for RUNNING timeout."""
    entry = (ps.get("steps") or {}).get(str(step)) or {}
    status = entry.get("status", "PENDING")
    if status == "RUNNING":
        at_str = entry.get("at", "")
        if at_str:
            try:
                at = datetime.fromisoformat(at_str)
                elapsed = (datetime.now(timezone.utc) - at).total_seconds()
                if elapsed > _RUNNING_TIMEOUT_SECS:
                    return "FAILED"
            except Exception:
                pass
    return status


def current_step(ps: dict | None) -> int:
    """First step (1..7) not COMPLETED; 8 when 1..7 are all done."""
    if not ps:
        return 1
    for s in range(1, 8):
        if step_status(ps, s) != "COMPLETED":
            return s
    return 8


# ── Public write API ──────────────────────────────────────────────────────────

def require_step(period: str, step: int) -> dict:
    """
    Raise RuntimeError if `step` cannot run now for `period`.
    Returns the period record on success.
    """
    data = _load_raw()
    ps = _period_record(data, period)
    if ps.get("closed_at"):
        raise RuntimeError(f"{period} is already closed")
    cur = current_step(ps)
    if step > cur:
        raise RuntimeError(
            f"{period}: finish step {cur} ({STEP_NAMES.get(cur, 'Close')}) before step {step}"
        )
    if step < cur and step_status(ps, step) == "COMPLETED":
        raise RuntimeError(f"{period}: step {step} already completed")
    return ps


def record_step(
    period: str,
    step: int,
    status: str,
    detail: dict | None = None,
    error: str | None = None,
    duration_ms: float = 0.0,
) -> None:
    with _LOCK:
        data = _load_raw()
        ps = _period_record(data, period)
        ps["steps"][str(step)] = {
            "step": step,
            "name": STEP_NAMES.get(step, f"Step {step}"),
            "status": status,
            "detail": detail or {},
            "error": error,
            "duration_ms": round(duration_ms, 1),
            "at": _now(),
        }
        ps["updated_at"] = _now()
        _save_raw(data)


def record_stage(
    period: str,
    stage: int,
    status: str,
    arg4: Any = None,
    arg5: Any = None,
    arg6: Any = None,
) -> None:
    """Backward compatibility shim mapping stage to record_step, handling both parameter orderings."""
    if isinstance(arg4, (int, float)):
        duration_ms = float(arg4)
        detail = arg5 if isinstance(arg5, dict) else None
        error = arg6 if isinstance(arg6, str) else None
    else:
        detail = arg4 if isinstance(arg4, dict) else None
        error = arg5 if isinstance(arg5, str) else None
        duration_ms = float(arg6) if isinstance(arg6, (int, float)) else 0.0
    record_step(period, stage, status, detail=detail, error=error, duration_ms=duration_ms)


def get_step_detail(period: str, step: int) -> dict:
    ps = _load_raw().get("periods", {}).get(period) or {}
    return (ps.get("steps") or {}).get(str(step), {}).get("detail", {})


def close_period(period: str) -> dict:
    with _LOCK:
        data = _load_raw()
        ps = _period_record(data, period)
        if ps.get("closed_at"):
            # Already closed — idempotent, return existing record
            return ps
        ps["closed_at"] = _now()
        ps["updated_at"] = ps["closed_at"]
        _save_raw(data)
        return ps


def reset_all() -> None:
    """Delete all cycle state and per-period artifact folders."""
    path = _state_path()
    if path.exists():
        path.unlink()
    # Delete per-period artifact folder
    cycle_dir = path.parent / "cycle"
    if cycle_dir.exists():
        import shutil
        shutil.rmtree(cycle_dir, ignore_errors=True)
    try:
        from app.store.cumulative import CumulativeStore
        CumulativeStore().reset_increments(confirm=True)
    except Exception as e:
        logger.warning(f"[CycleState] store.reset_increments failed: {e}")
    logger.info("[CycleState] All cycle state cleared.")


# ── Per-period artifact paths ─────────────────────────────────────────────────

def cycle_dir(period: str) -> Path:
    p = _state_path().parent / "cycle" / period
    p.mkdir(parents=True, exist_ok=True)
    return p


# ── Available periods (unchanged from original) ───────────────────────────────

def _available_periods() -> list[dict]:
    actuals_dir = resolve_actuals_dir()
    if not actuals_dir.exists():
        logger.warning(f"[CycleState] actuals_dir does not exist: {actuals_dir}. Run: make bootstrap")
        return []

    manifest_path = actuals_dir / "holdout_manifest.csv"
    if not manifest_path.exists():
        logger.warning(f"[CycleState] holdout_manifest.csv not found. Falling back to filesystem glob.")
        periods = []
        for f in sorted(actuals_dir.glob("????_??_actual.csv")):
            try:
                assert_real_file(f)
            except RuntimeError as lfs_err:
                logger.warning(f"[CycleState] Skipping LFS pointer: {lfs_err}")
                continue
            stem = f.stem
            parts = stem.split("_")
            if len(parts) >= 2:
                periods.append({"period": f"{parts[0]}-{parts[1]}", "filename": f.name, "rows": None})
        return periods

    try:
        assert_real_file(manifest_path)
    except (FileNotFoundError, RuntimeError) as e:
        logger.error(f"[CycleState] {e}")
        return []

    try:
        df = pd.read_csv(manifest_path)
    except Exception as e:
        logger.warning(f"[CycleState] manifest read failed: {e}")
        return []

    missing_cols = MANIFEST_REQUIRED_COLS - set(df.columns)
    if missing_cols:
        raise RuntimeError(
            f"[CycleState] holdout_manifest.csv is missing required columns: "
            f"{sorted(missing_cols)}. Run: make bootstrap"
        )

    periods = []
    for _, row in df.iterrows():
        split = str(row.get("split", "")).strip()
        if split == "train" or not split:
            continue
        period = split
        rows = int(row["rows"]) if pd.notna(row.get("rows")) else None
        filename = f"{period.replace('-', '_')}_actual.csv"
        csv_path = actuals_dir / filename
        if not csv_path.exists():
            continue
        try:
            assert_real_file(csv_path)
        except RuntimeError:
            continue
        periods.append({"period": period, "filename": filename, "rows": rows})

    return periods


# ── Main response builder ─────────────────────────────────────────────────────

def get_cycle_state_response() -> dict:
    """Build the full response for GET /api/v1/cycle/state."""
    from app.core.period import current_data_end
    from app.ml.registry import ModelRegistry
    from app.ml.utils import IntelligenceType

    all_ps = _load_raw().get("periods", {})
    available = _available_periods()

    trained_through = ""
    try:
        reg = ModelRegistry()
        v = reg.get_latest_version(IntelligenceType.DEMAND)
        if v:
            trained_through = getattr(v, "trained_through", "") or ""
            if not trained_through:
                trained_through = v.created_at[:7] if v.created_at else ""
    except Exception as e:
        logger.warning(f"[CycleState] trained_through lookup failed: {e}")

    # next_expected_period: earliest available period whose closed_at is None
    next_expected = None
    for ap in available:
        ps = all_ps.get(ap["period"], {})
        if not ps.get("closed_at"):
            next_expected = ap["period"]
            break

    completed_periods = {
        ap["period"] for ap in available
        if all_ps.get(ap["period"], {}).get("closed_at")
    }

    all_complete = len(available) > 0 and len(completed_periods) == len(available)

    period_entries = []
    for ap in available:
        period = ap["period"]
        ps = all_ps.get(period, {})
        steps = ps.get("steps", {})
        closed_at = ps.get("closed_at")
        ui_step = current_step(ps) if not closed_at else 8
        has_failed = any(
            (steps.get(str(s)) or {}).get("status") == "FAILED"
            for s in range(1, 8)
        )
        period_entries.append({
            "period": period,
            "filename": ap["filename"],
            "rows": ap["rows"],
            "ui_step": ui_step,
            "steps": steps,
            "closed_at": closed_at,
            "updated_at": ps.get("updated_at"),
            "is_complete": bool(closed_at),
            "has_failed_step": has_failed,
        })

    current_period = next_expected
    if current_period is None and available:
        current_period = available[-1]["period"]

    return {
        "current_period": current_period,
        "next_expected_period": next_expected,
        "trained_through": trained_through,
        "available_periods": period_entries,
        "step_names": STEP_NAMES,
        "stage_names": STEP_NAMES,
        "all_complete": all_complete,
        "total_available": len(available),
        "total_complete": len(completed_periods),
        "generated_at": _now(),
    }


def get_period_state(period: str) -> dict | None:
    """Backwards-compatibility shim returning the period record or None."""
    data = _load_raw()
    return data.get("periods", {}).get(period)


def get_all_periods() -> dict:
    """Backwards-compatibility shim returning all period records."""
    return _load_raw().get("periods", {})

"""
app/services/cycle_state_store.py
===================================
File-backed, backend-authoritative state machine for the forecast lifecycle.

One row per target period. The UI derives ALL lifecycle state from here.
No browser counter, no localStorage lifecycle values.

Stage numbering (matches the 7-stage canonical lifecycle):
  0  FORECAST_ISSUED   — forecast for P generated before actuals exist
  1  INGEST_VALIDATE   — actuals uploaded, schema + continuity checked
  2  MATCH             — actuals joined to standing forecast
  3  EVALUATE          — metrics computed on matched pairs
  4  TPKE_EVOLVE       — edges created / strengthened / decayed / pruned
  5  STORE_RETRAIN     — period appended, models retrained
  6  FORECAST_NEXT     — forecast for P+1 generated (= Stage 0 of next cycle)

Stage 6 of cycle N is Stage 0 of cycle N+1 — modelled once, referenced twice.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.core.data_files import assert_real_file, resolve_actuals_dir, MANIFEST_REQUIRED_COLS

logger = logging.getLogger(__name__)

_STAGE_NAMES = {
    0: "Forecast Issued",
    1: "Ingest & Validate",
    2: "Match",
    3: "Evaluate",
    4: "TPKE Evolve",
    5: "Store & Retrain",
    6: "Forecast Next",
}

_TERMINAL_STAGE = 6  # completing stage 6 closes the cycle


def _state_path() -> Path:
    settings = get_settings()
    p = Path(settings.model_dir).parent / "cycle_state.json"
    return p


def _load_raw() -> dict:
    path = _state_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[CycleState] load failed: {e}")
    return {"periods": {}}


def _save_raw(data: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── Public API ────────────────────────────────────────────────────────────────

def get_all_periods() -> dict[str, dict]:
    """Return {period: period_state} for all known periods."""
    return _load_raw().get("periods", {})


def get_period_state(period: str) -> dict | None:
    return get_all_periods().get(period)


def record_stage(
    period: str,
    stage: int,
    status: str,          # COMPLETED | SKIPPED | FAILED
    duration_ms: float,
    detail: dict[str, Any],
    error: str | None = None,
) -> None:
    """Record the outcome of a single stage for a period."""
    data = _load_raw()
    periods = data.setdefault("periods", {})
    if period not in periods:
        periods[period] = {
            "period": period,
            "stage_reached": -1,
            "stage_statuses": {},
            "forecast_run_id": None,
            "actuals_uploaded_at": None,
            "updated_at": None,
        }

    ps = periods[period]
    ps["stage_statuses"][str(stage)] = {
        "stage": stage,
        "name": _STAGE_NAMES.get(stage, f"Stage {stage}"),
        "status": status,
        "duration_ms": round(duration_ms, 1),
        "detail": detail,
        "error": error,
    }
    if status in ("COMPLETED", "SKIPPED") and stage > ps["stage_reached"]:
        ps["stage_reached"] = stage
    if stage == 1 and status == "COMPLETED":
        ps["actuals_uploaded_at"] = datetime.now(timezone.utc).isoformat()
    ps["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_raw(data)


def record_forecast_run_id(period: str, run_id: str) -> None:
    data = _load_raw()
    ps = data.setdefault("periods", {}).setdefault(period, {
        "period": period, "stage_reached": -1, "stage_statuses": {},
        "forecast_run_id": None, "actuals_uploaded_at": None, "updated_at": None,
    })
    ps["forecast_run_id"] = run_id
    ps["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_raw(data)


def reset_all() -> None:
    """Delete all cycle state. Called by POST /cycle/reset."""
    path = _state_path()
    if path.exists():
        path.unlink()
    try:
        from app.store.cumulative import CumulativeStore
        store = CumulativeStore()
        store.reset_increments(confirm=True)
    except Exception as e:
        logger.warning(f"[CycleState] store.reset_increments failed: {e}")
    logger.info("[CycleState] All cycle state cleared.")


# ── Derived queries ───────────────────────────────────────────────────────────

def _available_periods() -> list[dict]:
    """
    Return the holdout periods that have a CSV file in actuals_real/.
    Derived from holdout_manifest.csv — never hardcoded.

    Raises RuntimeError if the manifest is an LFS pointer or is missing
    required columns — a missing column must never be treated as zero rows.
    Falls back to filesystem glob when manifest is absent.
    """
    actuals_dir = resolve_actuals_dir()

    if not actuals_dir.exists():
        logger.warning(
            f"[CycleState] actuals_dir does not exist: {actuals_dir}. "
            "Run: make bootstrap"
        )
        return []

    manifest_path = actuals_dir / "holdout_manifest.csv"

    # ── No manifest: fall back to filesystem glob ─────────────────────────
    if not manifest_path.exists():
        logger.warning(
            f"[CycleState] holdout_manifest.csv not found in {actuals_dir}. "
            "Falling back to filesystem glob."
        )
        periods = []
        for f in sorted(actuals_dir.glob("????_??_actual.csv")):
            try:
                assert_real_file(f)
            except RuntimeError as lfs_err:
                logger.warning(f"[CycleState] Skipping LFS pointer: {lfs_err}")
                continue
            stem = f.stem  # e.g. "2017_10_actual"
            parts = stem.split("_")
            if len(parts) >= 2:
                period = f"{parts[0]}-{parts[1]}"
                periods.append({"period": period, "filename": f.name, "rows": None})
        logger.info(f"[CycleState] glob found {len(periods)} periods: {[p['period'] for p in periods]}")
        return periods

    # ── Manifest present: validate it before parsing ──────────────────────
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

    # Validate required columns — a DataFrame missing 'split' must RAISE,
    # not silently return zero rows.
    missing_cols = MANIFEST_REQUIRED_COLS - set(df.columns)
    if missing_cols:
        raise RuntimeError(
            f"[CycleState] holdout_manifest.csv is missing required columns: "
            f"{sorted(missing_cols)}. "
            f"Columns found: {sorted(df.columns.tolist())}. "
            f"This usually means the file is an LFS pointer or was regenerated "
            f"with a different schema. Run: make bootstrap"
        )

    periods = []
    skipped_train = 0
    skipped_no_file = 0
    skipped_lfs = 0

    for _, row in df.iterrows():
        split = str(row.get("split", "")).strip()
        if split == "train":
            skipped_train += 1
            continue
        if not split:
            logger.warning(f"[CycleState] manifest row has empty split value — skipping: {dict(row)}")
            continue

        period = split  # e.g. "2017-10"
        rows = int(row["rows"]) if pd.notna(row.get("rows")) else None
        filename = f"{period.replace('-', '_')}_actual.csv"
        csv_path = actuals_dir / filename

        if not csv_path.exists():
            skipped_no_file += 1
            logger.warning(f"[CycleState] actuals file not found for period {period}: {csv_path}")
            continue

        try:
            assert_real_file(csv_path)
        except RuntimeError as lfs_err:
            skipped_lfs += 1
            logger.warning(f"[CycleState] {lfs_err}")
            continue

        periods.append({"period": period, "filename": filename, "rows": rows})

    logger.info(
        f"[CycleState] _available_periods: {len(periods)} valid periods "
        f"(skipped train={skipped_train}, no_file={skipped_no_file}, lfs={skipped_lfs})"
    )
    if not periods:
        logger.warning(
            f"[CycleState] _available_periods returned empty list. "
            f"actuals_dir={actuals_dir}, manifest rows={len(df)}. "
            f"Check that actuals CSVs exist and are not LFS pointers."
        )
    return periods


def get_cycle_state_response() -> dict:
    """
    Build the full response for GET /api/v1/cycle/state.
    This is the single source of truth the UI reads.
    """
    from app.core.period import current_data_end
    from app.ml.registry import ModelRegistry
    from app.ml.utils import IntelligenceType

    all_ps = get_all_periods()
    available = _available_periods()

    # trained_through: from the active demand model registry entry
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

    # next_expected_period: earliest available period with no completed cycle
    completed_periods = {
        p for p, ps in all_ps.items()
        if ps.get("stage_reached", -1) >= _TERMINAL_STAGE
    }
    next_expected = None
    for ap in available:
        if ap["period"] not in completed_periods:
            next_expected = ap["period"]
            break

    # Build per-period entries
    period_entries = []
    for ap in available:
        period = ap["period"]
        ps = all_ps.get(period, {})
        stage_reached = ps.get("stage_reached", -1)
        stage_statuses = ps.get("stage_statuses", {})

        # can_upload: Stage 0 completed AND Stage 1 not yet completed
        stage0_done = stage_statuses.get("0", {}).get("status") == "COMPLETED"
        stage1_done = stage_statuses.get("1", {}).get("status") == "COMPLETED"
        can_upload = (period == next_expected) and stage0_done and not stage1_done

        # locked_reason: why a period cannot be acted on
        locked_reason = None
        if period != next_expected and stage_reached < _TERMINAL_STAGE:
            if next_expected:
                locked_reason = f"Upload {next_expected} first"
            else:
                locked_reason = "All cycles complete"

        period_entries.append({
            "period": period,
            "filename": ap["filename"],
            "rows": ap["rows"],
            "stage_reached": stage_reached,
            "stage_statuses": stage_statuses,
            "forecast_run_id": ps.get("forecast_run_id"),
            "actuals_uploaded_at": ps.get("actuals_uploaded_at"),
            "updated_at": ps.get("updated_at"),
            "can_upload": can_upload,
            "locked_reason": locked_reason,
            "is_complete": stage_reached >= _TERMINAL_STAGE,
        })

    # current_period: the period currently being worked on
    current_period = next_expected
    if current_period is None and available:
        current_period = available[-1]["period"]

    # all_complete: every available period has reached terminal stage
    all_complete = (
        len(available) > 0
        and all(
            all_ps.get(ap["period"], {}).get("stage_reached", -1) >= _TERMINAL_STAGE
            for ap in available
        )
    )

    # standing_forecast_period: the period the current standing forecast covers
    # = the period whose Stage 0 is COMPLETED but Stage 6 is not yet COMPLETED
    standing_forecast_period = None
    for ap in available:
        p = ap["period"]
        ps = all_ps.get(p, {})
        ss = ps.get("stage_statuses", {})
        stage0_done = ss.get("0", {}).get("status") == "COMPLETED"
        stage6_done = ss.get("6", {}).get("status") == "COMPLETED"
        if stage0_done and not stage6_done:
            standing_forecast_period = p
            break

    # awaiting_actuals_for: the period whose actuals upload is expected next
    # = next_expected (the earliest incomplete period)
    awaiting_actuals_for = next_expected

    return {
        "current_period": current_period,
        "next_expected_period": next_expected,
        "trained_through": trained_through,
        "available_periods": period_entries,
        "stage_names": _STAGE_NAMES,
        "all_complete": all_complete,
        "standing_forecast_period": standing_forecast_period,
        "awaiting_actuals_for": awaiting_actuals_for,
        "total_available": len(available),
        "total_complete": len(completed_periods),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

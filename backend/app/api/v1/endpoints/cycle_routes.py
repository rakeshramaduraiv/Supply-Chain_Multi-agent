"""
app/api/v1/endpoints/cycle_routes.py
=====================================
Backend-authoritative lifecycle endpoints — one endpoint per step.

GET  /cycle/state                 — full lifecycle state (UI source of truth)
GET  /cycle/preflight             — system readiness check
POST /cycle/{period}/forecast     — Step 1: generate forecast
GET  /cycle/{period}/forecast     — read stored forecast.json
POST /cycle/{period}/actuals      — Step 2: upload actuals CSV
POST /cycle/{period}/evaluate     — Step 3: actual vs predicted
POST /cycle/{period}/graph-update — Step 4: KG update (before RCA)
POST /cycle/{period}/rca          — Step 5: root cause analysis
GET  /cycle/{period}/rca          — read stored rca.json
POST /cycle/{period}/tpke         — Step 6: TPKE evolution
POST /cycle/{period}/learn        — Step 7: retrain + agent scores
POST /cycle/{period}/close        — Step 8: close period
POST /cycle/reset                 — wipe all cycle state
GET  /cycle/status                — legacy footer summary
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File

from app.services.cycle_store import get_latest_cycle_summary
from app.services.cycle_state_store import (
    get_cycle_state_response,
    record_step,
    require_step,
    close_period as _close_period,
    cycle_dir,
    reset_all as _reset_state,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cycle", tags=["Cycle"])


# ── Step guards ──────────────────────────────────────────────────────────────

def _guard(period: str, step: int) -> None:
    state = get_cycle_state_response()
    if state.get("next_expected_period") != period:
        raise HTTPException(409, f"{period} is not the active period")
    try:
        require_step(period, step)
    except RuntimeError as e:
        raise HTTPException(409, str(e))


async def _run_step(period: str, step: int, fn) -> dict:
    """fn is an async callable returning a detail dict."""
    _guard(period, step)
    record_step(period, step, "RUNNING")
    t0 = time.perf_counter()
    try:
        detail = await fn()
    except HTTPException as e:
        record_step(period, step, "FAILED", error=str(e.detail),
                    duration_ms=(time.perf_counter() - t0) * 1000)
        raise
    except Exception as e:
        logger.exception(f"cycle step {step} failed for {period}")
        record_step(period, step, "FAILED", error=str(e),
                    duration_ms=(time.perf_counter() - t0) * 1000)
        raise HTTPException(500, f"Step {step} failed: {e}")
    record_step(period, step, "COMPLETED", detail=detail,
                duration_ms=(time.perf_counter() - t0) * 1000)
    return {"period": period, "step": step, "status": "COMPLETED", "detail": detail}


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


# ── POST /cycle/advance/{period} (Removed — 410 Gone) ───────────────────────

@router.post("/advance/{period}", response_model=dict[str, Any])
async def advance_cycle(period: str):
    """Removed. Returns 410 Gone."""
    raise HTTPException(
        status_code=410,
        detail="POST /cycle/advance is no longer supported. Use step endpoints /cycle/{period}/* instead.",
    )


# ── POST /cycle/{period}/forecast  (Step 1) ──────────────────────────────────

@router.post("/{period}/forecast", response_model=dict[str, Any])
async def step1_forecast(period: str):
    """Step 1: Generate forecast for period and write forecast.json."""
    from app.api.v1.endpoints.dataset_summary import _compute_auto_forecast

    async def _fn():
        forecast = _compute_auto_forecast(target_period=period)
        if not forecast.get("ready"):
            raise HTTPException(422, {"message": forecast.get("message", "forecast not available"), "reason": "NOT_INITIALIZED"})
        out = cycle_dir(period) / "forecast.json"
        out.write_text(json.dumps(forecast, default=str), encoding="utf-8")
        return {
            "target_period": forecast.get("target_period", period),
            "trained_through": forecast.get("trained_through", ""),
            "categories": len(forecast.get("category_forecasts", [])),
        }

    return await _run_step(period, 1, _fn)


issue_forecast = step1_forecast  # alias for backwards compatibility


@router.get("/{period}/forecast", response_model=dict[str, Any])
async def get_forecast(period: str):
    """Return stored forecast.json for period."""
    p = cycle_dir(period) / "forecast.json"
    if not p.exists():
        raise HTTPException(404, f"No forecast for {period}")
    return json.loads(p.read_text(encoding="utf-8"))


# ── POST /cycle/{period}/actuals  (Step 2) ───────────────────────────────────

@router.post("/{period}/actuals", response_model=dict[str, Any])
async def step2_actuals(period: str, file: UploadFile = File(...)):
    """Step 2: Upload actuals CSV and write actuals.parquet."""
    import io
    from app.ingestion.schema_adapter import adapt
    raw = await file.read()

    async def _fn():
        df = pd.read_csv(io.BytesIO(raw))
        df.columns = [c.strip() for c in df.columns]
        df, schema_report = adapt(df)
        if not schema_report.ok:
            raise HTTPException(422, f"Missing columns: {schema_report.missing}")
        rejected = 0
        if "order date (DateOrders)" in df.columns:
            dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
            mask = dates.dt.strftime("%Y-%m") == period
            rejected = int((~mask).sum())
            if len(df) > 0 and rejected / len(df) > 0.05:
                raise HTTPException(
                    422,
                    f"{rejected}/{len(df)} rows ({rejected/len(df)*100:.1f}%) "
                    f"have dates outside {period} — exceeds 5% threshold"
                )
            df = df[mask].copy()
        out = cycle_dir(period) / "actuals.parquet"
        df.to_parquet(out, index=False)
        dates_col = pd.to_datetime(
            df.get("order date (DateOrders)", pd.Series(dtype="object")), errors="coerce"
        )
        return {
            "rows": len(df),
            "rejected_rows": rejected,
            "date_min": str(dates_col.min())[:10] if len(df) else None,
            "date_max": str(dates_col.max())[:10] if len(df) else None,
            "filename": file.filename,
        }

    return await _run_step(period, 2, _fn)


# ── POST /cycle/{period}/evaluate  (Step 3) ───────────────────────────────────

@router.post("/{period}/evaluate", response_model=dict[str, Any])
async def step3_evaluate(period: str):
    """Step 3: Aggregate actuals vs forecast and write evaluation.json."""
    import numpy as np
    from sklearn.metrics import (
        mean_absolute_error, mean_absolute_percentage_error,
        mean_squared_error, f1_score, precision_score, recall_score,
    )

    async def _fn():
        ap = cycle_dir(period) / "actuals.parquet"
        fp = cycle_dir(period) / "forecast.json"
        if not ap.exists():
            raise HTTPException(409, "actuals.parquet not found — run Step 2 first")
        if not fp.exists():
            raise HTTPException(409, "forecast.json not found — run Step 1 first")
        df = pd.read_parquet(ap)
        forecast = json.loads(fp.read_text(encoding="utf-8"))
        cat_forecasts = {(r["category"], r["region"]): r
                        for r in forecast.get("category_forecasts", [])}
        agg = df.groupby(["Category Name", "Order Region"]).agg(
            actual_demand=("Order Item Quantity", "sum"),
            late_rate=("Late_delivery_risk", "mean"),
            orders=("Order Item Quantity", "count"),
        ).reset_index()
        records = []
        for _, row in agg.iterrows():
            key = (row["Category Name"], row["Order Region"])
            fc = cat_forecasts.get(key)
            predicted = float(fc["predicted_demand"]) if fc and fc.get("predicted_demand") is not None else None
            actual = float(row["actual_demand"])
            dev = ((actual - predicted) / max(abs(predicted), 1)) * 100 if predicted is not None else None
            records.append({
                "category": row["Category Name"], "region": row["Order Region"],
                "predicted": predicted, "actual": actual,
                "deviation_pct": round(dev, 2) if dev is not None else None,
            })
        matched = [r for r in records if r["predicted"] is not None]
        forecast_keys = len(cat_forecasts)
        matched_keys = len(matched)
        match_rate = matched_keys / forecast_keys if forecast_keys else 0.0
        demand_mape = demand_mae = demand_rmse = None
        if matched:
            y_true = np.array([r["actual"] for r in matched])
            y_pred = np.array([r["predicted"] for r in matched])
            demand_mae = float(mean_absolute_error(y_true, y_pred))
            demand_rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
            demand_mape = float(mean_absolute_percentage_error(y_true, y_pred)) * 100
        late_f1 = late_prec = late_rec = late_reason = None
        try:
            import joblib
            from app.core.config import get_settings
            from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
            _s = get_settings()
            reg = json.loads((Path(_s.model_dir) / "registry.json").read_text())
            for it in (IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS):
                versions = reg.get(it.value, [])
                active = [v for v in versions if v.get("is_active")]
                if not active:
                    continue
                mi = active[-1]
                mp = Path(_s.model_dir).parent / mi["model_path"]
                if not mp.exists():
                    continue
                m = joblib.load(mp)
                feats = [f for f in (mi.get("features_used") or FEATURE_CONFIGS[it].features)
                         if f in df.columns]
                if not feats or "Late_delivery_risk" not in df.columns:
                    continue
                y_true_cls = df["Late_delivery_risk"].astype(int)
                if y_true_cls.nunique() < 2:
                    continue
                y_pred_cls = m.predict(df[feats].fillna(0))
                late_f1 = float(f1_score(y_true_cls, y_pred_cls, zero_division=0))
                late_prec = float(precision_score(y_true_cls, y_pred_cls, zero_division=0))
                late_rec = float(recall_score(y_true_cls, y_pred_cls, zero_division=0))
                break
        except Exception as e:
            late_reason = str(e)
        worst = max(matched, key=lambda r: abs(r["deviation_pct"] or 0), default=None)
        worst_dev = ({"category": worst["category"], "region": worst["region"],
                      "deviation_pct": worst["deviation_pct"]} if worst else None)
        buckets = {"within_5": 0, "minor_5_15": 0, "major_gt_15": 0}
        for r in matched:
            d = abs(r["deviation_pct"] or 0)
            if d <= 5:
                buckets["within_5"] += 1
            elif d <= 15:
                buckets["minor_5_15"] += 1
            else:
                buckets["major_gt_15"] += 1
        evaluation = {
            "period": period, "comparison_records": records,
            "matched_keys": matched_keys, "forecast_keys": forecast_keys,
            "match_rate": round(match_rate, 4),
            "demand_mape": round(demand_mape, 4) if demand_mape is not None else None,
            "demand_mae": round(demand_mae, 4) if demand_mae is not None else None,
            "demand_rmse": round(demand_rmse, 4) if demand_rmse is not None else None,
            "late_delivery_f1": round(late_f1, 4) if late_f1 is not None else None,
            "late_delivery_precision": round(late_prec, 4) if late_prec is not None else None,
            "late_delivery_recall": round(late_rec, 4) if late_rec is not None else None,
            "late_delivery_reason": late_reason,
            "worst_deviation": worst_dev, "buckets": buckets,
        }
        (cycle_dir(period) / "evaluation.json").write_text(
            json.dumps(evaluation, default=str), encoding="utf-8"
        )
        return {k: v for k, v in evaluation.items() if k != "comparison_records"}

    return await _run_step(period, 3, _fn)


# ── POST /cycle/{period}/graph-update  (Step 4) ───────────────────────────────

@router.post("/{period}/graph-update", response_model=dict[str, Any])
async def step4_graph_update(period: str):
    """Step 4: Write month-scoped Observation nodes into Neo4j."""
    from app.graph.actual_integration import ActualIntegrationLayer

    async def _fn():
        ap = cycle_dir(period) / "actuals.parquet"
        ep = cycle_dir(period) / "evaluation.json"
        if not ap.exists():
            raise HTTPException(409, "actuals.parquet not found")
        df = pd.read_parquet(ap)
        pred_map = {}
        if ep.exists():
            eval_data = json.loads(ep.read_text(encoding="utf-8"))
            pred_map = {(r["category"], r["region"]): r
                        for r in eval_data.get("comparison_records", [])}
        layer = ActualIntegrationLayer()
        return await layer.sync_actuals_scoped(df, period, pred_map)

    return await _run_step(period, 4, _fn)


# ── POST /cycle/{period}/rca  (Step 5) ────────────────────────────────────────

@router.post("/{period}/rca", response_model=dict[str, Any])
async def step5_rca(period: str):
    """Step 5: Run RCA on the updated graph and write rca.json."""
    from app.rca.services import RCAService
    from app.graph.rca_integration import RCAIntegrationLayer

    async def _fn():
        ep = cycle_dir(period) / "evaluation.json"
        if not ep.exists():
            raise HTTPException(409, "evaluation.json not found — run Step 3 first")
        evaluation = json.loads(ep.read_text(encoding="utf-8"))
        worst = evaluation.get("worst_deviation")
        if not worst:
            raise HTTPException(409, "No worst_deviation in evaluation")
        target_id = worst["category"]
        dev = worst.get("deviation_pct") or 0
        rca_type = "demand_spike" if dev > 0 else "late_delivery"
        service = RCAService()
        try:
            result = await service.analyze(
                target_id=target_id, target_label="Category",
                rca_type=rca_type, max_depth=3, top_n=10, period=period,
            )
        except ConnectionError as e:
            raise HTTPException(503, f"Neo4j unavailable: {e}")
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "RCA failed"))
        report = result["report"]
        sync_result = await RCAIntegrationLayer().sync_rca(report, period=period)
        rca_out = {"period": period, "target_id": target_id,
                   "rca_type": rca_type, "report": report}
        (cycle_dir(period) / "rca.json").write_text(
            json.dumps(rca_out, default=str), encoding="utf-8"
        )
        contributors = report.get("risk_contributors", [])
        return {
            "target_id": target_id, "rca_type": rca_type,
            "top_causes": [{"entity_id": c.get("entity_id", c.get("id", "")),
                            "score": c.get("score", 0), "confidence": c.get("confidence", 0)}
                           for c in contributors[:5]],
            "causes_written": sync_result.get("updated_relationships", 0),
        }

    return await _run_step(period, 5, _fn)


@router.get("/{period}/rca", response_model=dict[str, Any])
async def get_rca(period: str):
    """Return stored rca.json for period."""
    p = cycle_dir(period) / "rca.json"
    if not p.exists():
        raise HTTPException(404, f"No RCA report for {period}")
    return json.loads(p.read_text(encoding="utf-8"))


# ── POST /cycle/{period}/tpke  (Step 6) ───────────────────────────────────────

@router.post("/{period}/tpke", response_model=dict[str, Any])
async def step6_tpke(period: str):
    """Step 6: Run TPKE evolution with forecast + actuals + RCA."""
    from app.graph.connection import get_connection_manager
    from app.tpke.engine import TPKEEngine
    from app.database.postgres import async_session_factory

    async def _fn():
        fp = cycle_dir(period) / "forecast.json"
        ep = cycle_dir(period) / "evaluation.json"
        rp = cycle_dir(period) / "rca.json"
        if not fp.exists():
            raise HTTPException(409, "forecast.json not found")
        if not ep.exists():
            raise HTTPException(409, "evaluation.json not found")
        if not rp.exists():
            raise HTTPException(409, "rca.json not found — run Step 5 first")
        forecast = json.loads(fp.read_text(encoding="utf-8"))
        evaluation = json.loads(ep.read_text(encoding="utf-8"))
        rca = json.loads(rp.read_text(encoding="utf-8"))
        conn = get_connection_manager()
        async with async_session_factory() as session:
            engine = TPKEEngine(conn, session)
            report = await engine.run(
                forecast_data=forecast.get("category_forecasts", []),
                actual_data=evaluation.get("comparison_records", []),
                rca_report=rca.get("report", rca),
                triggered_by=f"cycle_{period}",
            )
        return {
            "edges_created": report.edges_created,
            "edges_strengthened": report.edges_strengthened,
            "edges_decayed": report.edges_decayed,
            "tpke_version": report.run_id,
        }

    return await _run_step(period, 6, _fn)


# ── POST /cycle/{period}/learn  (Step 7) ──────────────────────────────────────

@router.post("/{period}/learn", response_model=dict[str, Any])
async def step7_learn(period: str):
    """Step 7: Engineer features, append to cumulative store, retrain once."""
    import asyncio
    from app.core.config import get_settings
    from app.feature_engineering import engineer_features_on_test
    from app.ml.training import TrainingOrchestrator
    from app.store.cumulative import CumulativeStore
    from app.api.v1.endpoints.dataset_summary import clear_dataset_cache, clear_forecast_cache

    async def _fn():
        ap = cycle_dir(period) / "actuals.parquet"
        ep = cycle_dir(period) / "evaluation.json"
        if not ap.exists():
            raise HTTPException(409, "actuals.parquet not found")
        settings = get_settings()
        if not settings.retrain_on_upload:
            return {"retrain_skipped": True, "retrained_models": []}
        df_actual = pd.read_parquet(ap)
        evaluation = json.loads(ep.read_text(encoding="utf-8")) if ep.exists() else {}

        def _train():
            store = CumulativeStore()
            df_full = store.load_full()
            df_eng = engineer_features_on_test(df_actual, df_full)
            if period not in store.periods():
                report = store.append(df_eng, period)
                cumulative_rows = report.cumulative_rows
            else:
                cumulative_rows = len(store.load_full())
            results = TrainingOrchestrator().train_all(
                store.load_full(),
                dataset_version=f"cumulative_{period}",
                already_engineered=True,
                training_path="other",
            )
            return list(results.keys()), cumulative_rows

        retrained, cumulative_rows = await asyncio.to_thread(_train)
        clear_dataset_cache()
        clear_forecast_cache()
        agents = {}
        for agent in ("demand", "supplier", "logistics"):
            agents[agent] = {
                "score_on_period": evaluation.get("demand_mape"),
                "retrained": agent in retrained,
            }
        return {
            "retrained_models": retrained,
            "trained_through": period,
            "cumulative_rows": cumulative_rows,
            "agents": agents,
        }

    return await _run_step(period, 7, _fn)


# ── POST /cycle/{period}/close  (Step 8) ──────────────────────────────────────

@router.post("/{period}/close", response_model=dict[str, Any])
async def step8_close(period: str):
    """Step 8: Close period and advance to next."""
    from app.api.v1.endpoints.dataset_summary import clear_forecast_cache
    try:
        _close_period(period)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    clear_forecast_cache()
    state = get_cycle_state_response()
    return {
        "closed": period,
        "next_period": state.get("next_expected_period"),
        "all_complete": state.get("all_complete", False),
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


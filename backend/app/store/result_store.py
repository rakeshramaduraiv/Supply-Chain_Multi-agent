"""
AMASCI Result Store
====================
Persists all data-flow processed results to CSV files under data/results/.
Each flow has its own CSV; rows are appended so history accumulates.
Any consumer can read these CSVs to reuse the computed values.

Files written:
  data/results/auto_forecast.csv          — per-category forecast results
  data/results/error_diagnostics.csv      — predicted vs actual diagnostics
  data/results/rca_investigations.csv     — RCA incident analysis summaries
  data/results/counterfactual_scenarios.csv — counterfactual simulation results
  data/results/tpke_evolutions.csv        — TPKE evolution cycle results
  data/results/tpke_decay.csv             — TPKE decay pass results
  data/results/closed_loop_cycles.csv     — closed-loop orchestrator cycle results
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_RESULTS_DIR = Path("data/results")


def _dir() -> Path:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return _RESULTS_DIR


def _append(filename: str, rows: list[dict[str, Any]]) -> None:
    """Append rows to a CSV, creating it with headers if it doesn't exist."""
    if not rows:
        return
    try:
        path = _dir() / filename
        df_new = pd.DataFrame(rows)
        if path.exists():
            df_new.to_csv(path, mode="a", header=False, index=False)
        else:
            df_new.to_csv(path, index=False)
        logger.debug(f"[ResultStore] Appended {len(rows)} rows → {filename}")
    except Exception as e:
        logger.warning(f"[ResultStore] Failed to write {filename}: {e}")


def _overwrite(filename: str, rows: list[dict[str, Any]]) -> None:
    """Overwrite CSV with latest full result set (for caches that replace on each run)."""
    if not rows:
        return
    try:
        pd.DataFrame(rows).to_csv(_dir() / filename, index=False)
        logger.debug(f"[ResultStore] Wrote {len(rows)} rows → {filename}")
    except Exception as e:
        logger.warning(f"[ResultStore] Failed to write {filename}: {e}")


def read(filename: str) -> pd.DataFrame | None:
    """Read a result CSV back as a DataFrame. Returns None if file doesn't exist."""
    path = _dir() / filename
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as e:
        logger.warning(f"[ResultStore] Failed to read {filename}: {e}")
        return None


# ── Auto-Forecast ─────────────────────────────────────────────────────────────

def save_auto_forecast(forecast: dict[str, Any]) -> None:
    """Persist auto-forecast category results. Overwrites on each new forecast run."""
    if not forecast.get("ready"):
        return
    ts = datetime.now(timezone.utc).isoformat()
    period = forecast.get("forecast_period", "")
    rows = []
    for cf in forecast.get("category_forecasts", []):
        rows.append({
            "saved_at": ts,
            "forecast_period": period,
            "overall_confidence": forecast.get("overall_confidence"),
            "category": cf.get("category"),
            "region": cf.get("region"),
            "order_count": cf.get("order_count"),
            "predicted_demand": cf.get("predicted_demand"),
            "predicted_revenue": cf.get("predicted_revenue"),
            "combined_risk": cf.get("combined_risk"),
            "demand_risk": cf.get("demand_risk"),
            "supplier_risk": cf.get("supplier_risk"),
            "logistics_risk": cf.get("logistics_risk"),
        })
    _overwrite("auto_forecast.csv", rows)


# ── Error Diagnostics ─────────────────────────────────────────────────────────

def save_error_diagnostics(result: dict[str, Any], period: str | None = None) -> None:
    """Append error diagnostics run to CSV."""
    ts = datetime.now(timezone.utc).isoformat()
    rows = []
    for d in result.get("diagnostics", []):
        rows.append({
            "saved_at": ts,
            "period": period or d.get("period", "latest"),
            "category": d.get("category"),
            "region": d.get("region"),
            "predicted_demand": d.get("predicted_demand"),
            "actual_demand": d.get("actual_demand"),
            "variance": d.get("variance"),
            "responsible_agent": d.get("responsible_agent"),
            "risk_level": d.get("risk_level"),
            "late_delivery_rate": d.get("late_delivery_rate"),
            "reason": d.get("reason"),
            "root_cause": d.get("root_cause"),
        })
    _append("error_diagnostics.csv", rows)


# ── RCA Investigations ────────────────────────────────────────────────────────

def save_rca_investigation(result: dict[str, Any]) -> None:
    """Append RCA investigation summary to CSV."""
    if not result.get("success"):
        return
    ts = datetime.now(timezone.utc).isoformat()
    impact = result.get("report", {}).get("business_impact", {})
    rows = [{
        "saved_at": ts,
        "incident_id": result.get("incident_id"),
        "target_id": result.get("target_id"),
        "target_label": result.get("target_label"),
        "rca_type": result.get("rca_type"),
        "primary_root_cause": result.get("report", {}).get("primary_root_cause"),
        "decision_confidence": result.get("report", {}).get("decision_confidence"),
        "financial_loss": impact.get("financial_loss"),
        "affected_orders": impact.get("affected_orders"),
        "affected_customers": impact.get("affected_customers"),
        "expected_delay": impact.get("expected_delay"),
        "revenue_impact": impact.get("revenue_impact"),
        "recovery_time_days": impact.get("recovery_time_days"),
        "top_evidence": result.get("evidence_ranking", [{}])[0].get("evidence", "") if result.get("evidence_ranking") else "",
    }]
    _append("rca_investigations.csv", rows)


# ── Counterfactual Scenarios ──────────────────────────────────────────────────

def save_counterfactual(result: dict[str, Any]) -> None:
    """Append counterfactual simulation scenarios to CSV."""
    if not result.get("success"):
        return
    ts = datetime.now(timezone.utc).isoformat()
    rows = []
    for s in result.get("all_scenarios", []):
        rows.append({
            "saved_at": ts,
            "target_id": result.get("target_id"),
            "primary_supplier": result.get("primary_supplier"),
            "alternative_supplier": result.get("alternative_supplier"),
            "allocation_shift_pct": result.get("allocation_shift_pct"),
            "scenario_id": s.get("id"),
            "scenario_name": s.get("name"),
            "delay_reduction_days": s.get("delay_reduction_days"),
            "cost_delta": s.get("cost_delta"),
            "risk_reduction_pct": s.get("risk_reduction_pct"),
            "financial_savings": s.get("financial_savings"),
            "decision_confidence": s.get("decision_confidence"),
            "recommended": s.get("recommended"),
        })
    _append("counterfactual_scenarios.csv", rows)


# ── TPKE Evolution ────────────────────────────────────────────────────────────

def save_tpke_evolution(report: dict[str, Any], triggered_by: str = "") -> None:
    """Append TPKE evolution cycle summary to CSV."""
    ts = datetime.now(timezone.utc).isoformat()
    rows = [{
        "saved_at": ts,
        "triggered_by": triggered_by,
        "edges_created": report.get("edges_created", 0),
        "edges_strengthened": report.get("edges_strengthened", 0),
        "edges_decayed": report.get("edges_decayed", 0),
        "edges_removed": report.get("edges_removed", 0),
        "patterns_detected": report.get("patterns_detected", 0),
        "graph_version": report.get("graph_version", ""),
        "duration_ms": report.get("duration_ms", 0),
    }]
    _append("tpke_evolutions.csv", rows)


def save_tpke_decay(result: dict[str, Any]) -> None:
    """Append TPKE decay pass result to CSV."""
    ts = datetime.now(timezone.utc).isoformat()
    rows = [{
        "saved_at": ts,
        "edges_decayed": result.get("edges_decayed", 0),
        "edges_removed": result.get("edges_removed", 0),
        "mutations_count": len(result.get("mutations", [])),
    }]
    _append("tpke_decay.csv", rows)


# ── Closed-Loop Cycles ────────────────────────────────────────────────────────

def save_closed_loop_cycle(result: dict[str, Any]) -> None:
    """Append closed-loop orchestrator cycle result to CSV."""
    ts = datetime.now(timezone.utc).isoformat()
    rows = [{
        "saved_at": ts,
        "cycle_id": result.get("cycle_id"),
        "timestamp": result.get("timestamp"),
        "dataset_processed": result.get("dataset_processed"),
        "nodes_updated": result.get("nodes_updated"),
        "rca_generated": result.get("rca_generated"),
        "tpke_mutations": result.get("tpke_mutations"),
        "graphrag_validated": result.get("graphrag_validated"),
        "agent_memory_updated": result.get("agent_memory_updated"),
        "duration_ms": result.get("duration_ms"),
        "recommendations": " | ".join(result.get("business_recommendation", [])),
    }]
    _append("closed_loop_cycles.csv", rows)

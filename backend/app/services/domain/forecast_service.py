"""Forecast Service - Run management and result retrieval."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.domain import ForecastRunRepository, ForecastResultRepository
from app.services import BaseService

logger = logging.getLogger(__name__)


class ForecastService(BaseService):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.run_repo = ForecastRunRepository(session)
        self.result_repo = ForecastResultRepository(session)

    async def create_run(
        self,
        name: str,
        dataset_id: str,
        model_id: str,
        horizon_days: int = 30,
        parameters: dict | None = None,
        triggered_by: str | None = None,
    ) -> dict:
        run = await self.run_repo.create(
            name=name,
            dataset_id=dataset_id,
            model_id=model_id,
            forecast_horizon_days=horizon_days,
            parameters_json=parameters,
            triggered_by=triggered_by,
            status="pending",
        )
        return {"id": run.id, "name": run.name, "status": run.status}

    async def complete_run(self, run_id: str, total_predictions: int, avg_confidence: float, duration_ms: float) -> dict:
        run = await self.run_repo.update_by_id(
            run_id,
            status="completed",
            total_predictions=total_predictions,
            avg_confidence=avg_confidence,
            duration_ms=duration_ms,
        )
        return {"id": run_id, "status": "completed", "total_predictions": total_predictions}

    async def fail_run(self, run_id: str, error: str) -> None:
        await self.run_repo.update_by_id(run_id, status="failed", error_message=error)

    async def add_results(self, run_id: str, results: list[dict]) -> int:
        for r in results:
            await self.result_repo.create(forecast_run_id=run_id, **r)
        return len(results)

    async def get_run(self, run_id: str) -> dict | None:
        run = await self.run_repo.get_by_id(run_id)
        if not run:
            return None
        return {
            "id": run.id, "name": run.name, "status": run.status,
            "total_predictions": run.total_predictions, "avg_confidence": run.avg_confidence,
            "forecast_horizon_days": run.forecast_horizon_days, "duration_ms": run.duration_ms,
            "created_at": str(run.created_at),
        }

    async def list_runs(self, status: str | None = None, skip: int = 0, limit: int = 50) -> list[dict]:
        if status:
            runs = await self.run_repo.get_by_status(status, skip=skip, limit=limit)
        else:
            runs = await self.run_repo.get_all(skip=skip, limit=limit)
        return [{"id": r.id, "name": r.name, "status": r.status, "created_at": str(r.created_at)} for r in runs]

    async def get_results(self, run_id: str, skip: int = 0, limit: int = 1000) -> list[dict]:
        results = await self.result_repo.get_by_run(run_id, skip=skip, limit=limit)
        return [
            {
                "id": r.id, "entity_id": r.entity_id, "entity_type": r.entity_type,
                "forecast_date": str(r.forecast_date), "predicted_value": r.predicted_value,
                "confidence_score": r.confidence_score, "risk_flag": r.risk_flag,
            }
            for r in results
        ]

    async def get_risk_alerts(self, run_id: str) -> list[dict]:
        results = await self.result_repo.get_risk_flagged(run_id)
        return [
            {"entity_id": r.entity_id, "entity_type": r.entity_type, "predicted_value": r.predicted_value, "confidence_score": r.confidence_score}
            for r in results
        ]

    async def run_graph_aware_forecast(
        self,
        df: pd.DataFrame,
        period_start: str,
        period_end: str,
        run_id: str,
    ) -> dict[str, Any]:
        """
        Executes the full graph-aware multi-agent forecast pipeline.

        GraphRAG is called ONCE per (Category, Region) group.
        The resulting context dict is shared by ALL FOUR agents.
        This is the Knowledge Graph → ML Agent bridge.

        Flow per group:
          1. GraphRAG.get_forecast_context(category, region)  [ONE call]
          2. Demand    Agent .predict(group_df, graph_context)
          3. Inventory Agent .predict(group_df, graph_context)
          4. Supplier  Agent .predict(group_df, graph_context)
          5. Logistics Agent .predict(group_df, graph_context)
          6. Combine → weighted risk score → persist
        """
        from app.graphrag.graph_context import GraphContextService
        from app.ml.prediction import (
            DemandAgent, InventoryAgent,
            SupplierAgent, LogisticsAgent,
        )
        from datetime import datetime, timezone

        graph_svc = GraphContextService()
        demand    = DemandAgent()
        inventory = InventoryAgent()
        supplier  = SupplierAgent()
        logistics = LogisticsAgent()

        forecast_generated_at = datetime.now(timezone.utc).isoformat()

        group_cols = [c for c in ["Category Name", "Order Region"] if c in df.columns]
        if not group_cols:
            raise ValueError("Cannot group — Category Name / Order Region missing")

        results = []
        skipped = 0

        for group_key, group_df in df.groupby(group_cols):
            category = group_key[0] if isinstance(group_key, tuple) else str(group_key)
            region   = group_key[1] if isinstance(group_key, tuple) and len(group_key) > 1 else "Unknown"

            if len(group_df) < 5:
                skipped += 1
                continue

            # ── STEP 1: ONE GraphRAG call per group ────────────────
            try:
                graph_context = await graph_svc.get_agent_context(
                    category=category, region=region
                )
            except Exception as e:
                logger.warning(f"GraphRAG failed for {category}/{region}: {e}")
                graph_context = self._empty_graph_context(category, region)

            # ── STEP 2: All 4 agents receive the SAME context ──────
            try:
                d_out = demand.predict(group_df, graph_context=graph_context)
                i_out = inventory.predict(group_df, graph_context=graph_context)
                s_out = supplier.predict(group_df, graph_context=graph_context)
                l_out = logistics.predict(group_df, graph_context=graph_context)
            except Exception as e:
                logger.error(f"Agent prediction failed for {category}/{region}: {e}")
                continue

            # ── STEP 3: Weighted consensus ─────────────────────────
            d_risk = float(np.mean(d_out.predictions)) if d_out.predictions else 0.0
            i_risk = float(np.mean(i_out.probabilities or [0.5]))
            s_risk = float(np.mean(s_out.probabilities or [0.5]))
            l_risk = float(np.mean(l_out.probabilities or [0.5]))

            combined = (
                0.25 * min(d_risk / max(d_risk, 1.0), 1.0)
                + 0.25 * i_risk
                + 0.30 * s_risk
                + 0.20 * l_risk
            )
            level = "High" if combined > 0.65 else "Medium" if combined > 0.35 else "Low"

            results.append({
                "category": category,
                "region": region,
                "period_start": period_start,
                "period_end": period_end,
                "demand_forecast": round(d_risk, 2),
                "confidence_lower": d_out.confidence_lower[0] if d_out.confidence_lower else None,
                "confidence_upper": d_out.confidence_upper[0] if d_out.confidence_upper else None,
                "inventory_stockout_risk": round(i_risk, 4),
                "supplier_risk_score": round(s_risk, 4),
                "logistics_risk_score": round(l_risk, 4),
                "combined_risk_score": round(combined, 4),
                "overall_risk_level": level,
                "graph_context_used": bool(graph_context.get("entities")),
                "graph_context_summary": graph_context.get("summary", ""),
                "graph_amplification": {
                    "demand":    d_out.graph_amplification,
                    "inventory": i_out.graph_amplification,
                    "supplier":  s_out.graph_amplification,
                },
                # Issue #9: Staleness tracking
                "forecast_generated_at": forecast_generated_at,
                "cold_start": graph_context.get("_cold_start", False),
            })

        logger.info(
            f"Forecast complete: {len(results)} groups predicted, "
            f"{skipped} skipped (too small)"
        )

        return {
            "run_id": run_id,
            "period": f"{period_start} to {period_end}",
            "total_forecasts": len(results),
            "groups_skipped": skipped,
            "forecasts": results,
            "high_risk_count": sum(
                1 for r in results if r["overall_risk_level"] == "High"
            ),
        }

    @staticmethod
    def _empty_graph_context(category: str, region: str) -> dict[str, Any]:
        """Safe neutral defaults when the Knowledge Graph has no data."""
        return {
            "summary": f"No graph context for '{category}' in '{region}'",
            "avg_supplier_reliability": 0.5,
            "inventory_stress": 0.5,
            "avg_shipping_delay": 0.0,
            "demand_volatility": 0.3,
            "upcoming_events": [],
            "holiday_risk_events": [],
            "amplified_supplier_count": 0,
            "entities": [],
        }

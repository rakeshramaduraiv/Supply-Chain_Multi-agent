"""
AMASCI Actual Integration Layer
================================
Ingests actual operational outcomes into Neo4j as month-scoped Observation
nodes.  No edge-weight mutation on the base graph — that would contaminate
the training-time graph with holdout-period signals.

Only sync_actuals_scoped() is called by the cycle (Step 4).
sync_actuals() is kept for legacy callers but is NOT called by the cycle.
auto_sync_actuals() fabricated fallback is removed.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.graph.connection import Neo4jConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


# Month-scoped Observation nodes — one node per (period, node_id).
# MERGE ensures idempotency: re-running Step 4 for the same period is safe.
_UPSERT_OBSERVATIONS = """
UNWIND $batch AS row
MERGE (o:Observation {period: row.period, node_id: row.node_id})
ON CREATE SET
    o.created_at      = row.ts,
    o.actual_demand   = row.actual_demand,
    o.actual_late_rate = row.actual_late_rate,
    o.predicted_demand = row.predicted_demand,
    o.deviation_pct   = row.deviation_pct,
    o.orders          = row.orders
ON MATCH SET
    o.updated_at      = row.ts,
    o.actual_demand   = row.actual_demand,
    o.actual_late_rate = row.actual_late_rate,
    o.predicted_demand = row.predicted_demand,
    o.deviation_pct   = row.deviation_pct,
    o.orders          = row.orders
WITH o, row
MATCH (ref)
WHERE ref.name = row.node_id OR ref.node_id = row.node_id
MERGE (ref)-[:HAS_OBSERVATION {period: row.period}]->(o)
RETURN count(o) AS upserted
"""

# Legacy node-property update — kept for non-cycle callers only.
_UPDATE_ACTUAL_PROPERTIES = """
UNWIND $batch AS p
MATCH (n) WHERE n.node_id = p.node_id OR n.id = p.node_id OR n.name = p.node_id
SET n.latest_actual_timestamp = p.timestamp,
    n.actual_demand = p.actual_demand,
    n.actual_delay_days = p.actual_delay_days,
    n.actual_late_delivery = p.actual_late_delivery
RETURN count(n) AS updated
"""


class ActualIntegrationLayer:

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    # ── Cycle Step 4 ──────────────────────────────────────────────────────────

    async def sync_actuals_scoped(
        self,
        df: pd.DataFrame,
        period: str,
        pred_map: dict | None = None,
    ) -> dict[str, Any]:
        """
        Write month-scoped Observation nodes for `period`.

        Aggregates df by Category, Department, and Route then MERGEs one
        Observation node per (period, node_id).  Never mutates base-graph
        edge weights — no data leakage from holdout months into the training
        graph.

        pred_map: {(category, region): evaluation_record} from evaluation.json
        """
        ts = datetime.now(timezone.utc).isoformat()
        pred_map = pred_map or {}

        if df.empty:
            return {"observations_upserted": 0, "period": period, "timestamp": ts}

        batch: list[dict] = []

        # Category-level aggregation
        if "Category Name" in df.columns and "Order Item Quantity" in df.columns:
            cat_agg = df.groupby("Category Name").agg(
                actual_demand=("Order Item Quantity", "sum"),
                actual_late_rate=("Late_delivery_risk", "mean") if "Late_delivery_risk" in df.columns else ("Order Item Quantity", "count"),
                orders=("Order Item Quantity", "count"),
            ).reset_index()
            for _, row in cat_agg.iterrows():
                node_id = str(row["Category Name"])
                # Find a matching prediction (any region for this category)
                pred = next(
                    (v for (cat, _), v in pred_map.items() if cat == node_id),
                    None,
                )
                batch.append({
                    "period": period,
                    "node_id": node_id,
                    "ts": ts,
                    "actual_demand": float(row["actual_demand"]),
                    "actual_late_rate": float(row.get("actual_late_rate", 0.0)),
                    "predicted_demand": float(pred["predicted"]) if pred and pred.get("predicted") is not None else None,
                    "deviation_pct": float(pred["deviation_pct"]) if pred and pred.get("deviation_pct") is not None else None,
                    "orders": int(row["orders"]),
                })

        # Department-level aggregation
        if "Department Name" in df.columns and "Order Item Quantity" in df.columns:
            dept_agg = df.groupby("Department Name").agg(
                actual_demand=("Order Item Quantity", "sum"),
                actual_late_rate=("Late_delivery_risk", "mean") if "Late_delivery_risk" in df.columns else ("Order Item Quantity", "count"),
                orders=("Order Item Quantity", "count"),
            ).reset_index()
            for _, row in dept_agg.iterrows():
                batch.append({
                    "period": period,
                    "node_id": f"DEPT_{row['Department Name']}",
                    "ts": ts,
                    "actual_demand": float(row["actual_demand"]),
                    "actual_late_rate": float(row.get("actual_late_rate", 0.0)),
                    "predicted_demand": None,
                    "deviation_pct": None,
                    "orders": int(row["orders"]),
                })

        # Route-level aggregation (Order Region + Shipping Mode)
        if "Order Region" in df.columns and "Shipping Mode" in df.columns:
            route_agg = df.groupby(["Order Region", "Shipping Mode"]).agg(
                actual_late_rate=("Late_delivery_risk", "mean") if "Late_delivery_risk" in df.columns else ("Order Item Quantity", "count"),
                orders=("Order Item Quantity", "count") if "Order Item Quantity" in df.columns else ("Order Region", "count"),
            ).reset_index()
            for _, row in route_agg.iterrows():
                batch.append({
                    "period": period,
                    "node_id": f"ROUTE_{row['Order Region']}_{row['Shipping Mode']}".replace(" ", "_"),
                    "ts": ts,
                    "actual_demand": None,
                    "actual_late_rate": float(row.get("actual_late_rate", 0.0)),
                    "predicted_demand": None,
                    "deviation_pct": None,
                    "orders": int(row["orders"]),
                })

        if not batch:
            return {"observations_upserted": 0, "period": period, "timestamp": ts}

        try:
            result = await self._conn.execute_write(_UPSERT_OBSERVATIONS, {"batch": batch})
            upserted = result[0]["upserted"] if result else len(batch)
        except Exception as e:
            logger.error(f"[ActualIntegration] sync_actuals_scoped failed for {period}: {e}")
            raise

        logger.info(
            f"[ActualIntegration] {period}: {upserted} Observation nodes upserted "
            f"({len(batch)} batch items)"
        )
        return {"observations_upserted": upserted, "period": period, "timestamp": ts}

    # ── Legacy (non-cycle) ────────────────────────────────────────────────────

    async def sync_actuals(
        self,
        actual_records: list[dict[str, Any]],
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """
        Legacy node-property update.  NOT called by the cycle.
        Does not mutate edge weights (removed to prevent holdout leakage).
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        if not actual_records:
            return {"updated": 0, "timestamp": ts}

        batch = [
            {
                "node_id": str(r.get("node_id", r.get("Category Name", "DEFAULT"))),
                "timestamp": ts,
                "actual_demand": float(r.get("actual_demand_7d", r.get("Sales", 0.0))),
                "actual_delay_days": float(r.get("actual_delay_days", r.get("shipping_delay", 0.0))),
                "actual_late_delivery": int(r.get("actual_late_delivery", r.get("Late_delivery_risk", 0))),
            }
            for r in actual_records
        ]

        try:
            records = await self._conn.execute_write(_UPDATE_ACTUAL_PROPERTIES, {"batch": batch})
            updated = records[0]["updated"] if records else 0
        except Exception as e:
            logger.warning(f"[ActualIntegration] sync_actuals note: {e}")
            updated = 0

        return {"updated": updated, "timestamp": ts}

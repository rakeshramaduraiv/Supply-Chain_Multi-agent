"""
AMASCI Actual Integration Layer
================================
Ingests actual operational outcomes into Neo4j as month-scoped
Observation nodes. Does NOT overwrite node properties and does NOT
compound edge weights (edge evolution belongs to TPKE Step 6 only).
"""

import logging
from datetime import datetime, timezone
from typing import Any
import pandas as pd

from app.graph.connection import Neo4jConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


_UPSERT_OBSERVATIONS = """
UNWIND $batch AS p
MATCH (n) WHERE n.node_id = p.node_id OR n.id = p.node_id OR n.name = p.node_id
MERGE (o:Observation {period: $period, node_id: p.node_id})
SET o.actual_demand    = p.actual_demand,
    o.late_rate        = p.late_rate,
    o.avg_delay_days   = p.avg_delay_days,
    o.orders           = p.orders,
    o.predicted_demand = p.predicted_demand,
    o.deviation_pct    = p.deviation_pct,
    o.updated_at       = $ts
MERGE (o)-[:OBSERVED_FOR]->(n)
RETURN count(DISTINCT n) AS nodes_matched
"""

_GRAPH_VERSION = """
MERGE (meta:_GraphMeta {key: 'active_version'})
ON CREATE SET meta.version = 1, meta.updated_at = $ts, meta.last_trigger = 'graph_update'
ON MATCH  SET meta.version = coalesce(meta.version, 0) + 1,
              meta.updated_at = $ts, meta.last_trigger = 'graph_update'
RETURN meta.version AS version
"""


class ActualIntegrationLayer:
    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def sync_actuals_scoped(
        self,
        df: pd.DataFrame,
        period: str,
        pred_map: dict[tuple, dict] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """
        Write month-scoped Observation nodes for every Category, Department
        and Shipping-Mode|Region combination in df.
        pred_map: {(category, region): evaluation_record} from evaluation.json.
        Raises on Neo4j errors so the cycle step is marked FAILED.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        if df is None or len(df) == 0:
            return {"updated": 0, "reason": "no actuals", "period": period}

        pred_map = pred_map or {}
        batch: list[dict] = []

        # Category aggregation
        if "Category Name" in df.columns:
            for cat, grp in df.groupby("Category Name"):
                orders = len(grp)
                actual_demand = float(grp["Order Item Quantity"].sum()) if "Order Item Quantity" in grp.columns else 0.0
                late_rate = float(grp["Late_delivery_risk"].mean()) if "Late_delivery_risk" in grp.columns else 0.0
                avg_delay = float(grp["shipping_delay_days"].mean()) if "shipping_delay_days" in grp.columns else 0.0
                # best-effort join to evaluation
                region_keys = [k for k in pred_map if k[0] == cat]
                predicted = float(sum(pred_map[k].get("predicted") or 0 for k in region_keys)) if region_keys else None
                deviation = float(sum(pred_map[k].get("deviation_pct") or 0 for k in region_keys) / len(region_keys)) if region_keys else None
                batch.append({
                    "node_id": str(cat),
                    "actual_demand": actual_demand, "late_rate": late_rate,
                    "avg_delay_days": avg_delay, "orders": orders,
                    "predicted_demand": predicted, "deviation_pct": deviation,
                })

        # Department (supplier proxy) aggregation
        if "Department Name" in df.columns:
            for dept, grp in df.groupby("Department Name"):
                batch.append({
                    "node_id": str(dept),
                    "actual_demand": float(grp["Order Item Quantity"].sum()) if "Order Item Quantity" in grp.columns else 0.0,
                    "late_rate": float(grp["Late_delivery_risk"].mean()) if "Late_delivery_risk" in grp.columns else 0.0,
                    "avg_delay_days": float(grp["shipping_delay_days"].mean()) if "shipping_delay_days" in grp.columns else 0.0,
                    "orders": len(grp), "predicted_demand": None, "deviation_pct": None,
                })

        # Route (Shipping Mode | Order Region) aggregation
        if "Shipping Mode" in df.columns and "Order Region" in df.columns:
            df["_route"] = df["Shipping Mode"].astype(str) + "|" + df["Order Region"].astype(str)
            for route, grp in df.groupby("_route"):
                batch.append({
                    "node_id": str(route),
                    "actual_demand": float(grp["Order Item Quantity"].sum()) if "Order Item Quantity" in grp.columns else 0.0,
                    "late_rate": float(grp["Late_delivery_risk"].mean()) if "Late_delivery_risk" in grp.columns else 0.0,
                    "avg_delay_days": float(grp["shipping_delay_days"].mean()) if "shipping_delay_days" in grp.columns else 0.0,
                    "orders": len(grp), "predicted_demand": None, "deviation_pct": None,
                })

        if not batch:
            return {"updated": 0, "reason": "no aggregatable columns", "period": period}

        # Raises on error — caller marks step FAILED
        records = await self._conn.execute_write(_UPSERT_OBSERVATIONS, {"batch": batch, "period": period, "ts": ts})
        nodes_matched = records[0]["nodes_matched"] if records else 0

        ver_res = await self._conn.execute_write(_GRAPH_VERSION, {"ts": ts})
        graph_version = ver_res[0].get("version") if ver_res and isinstance(ver_res[0], dict) else None

        all_ids = {r["node_id"] for r in batch}
        # nodes_unmatched: ids in batch that didn't match (approximate — Neo4j returns matched count)
        nodes_unmatched = list(all_ids)[:20] if nodes_matched == 0 else []

        logger.info(f"[ActualIntegration] period={period} observations={len(batch)} nodes_matched={nodes_matched}")
        return {
            "period": period,
            "observations_written": len(batch),
            "nodes_matched": nodes_matched,
            "nodes_unmatched": nodes_unmatched,
            "graph_version": graph_version,
        }

    # Keep legacy sync_actuals for backward compat (used by old routes)
    async def sync_actuals(
        self,
        actual_records: list[dict[str, Any]],
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        if not actual_records:
            return {"updated": 0, "reason": "no actuals"}
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        df = pd.DataFrame(actual_records)
        return await self.sync_actuals_scoped(df, period="legacy", timestamp=ts)


async def auto_sync_actuals(df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Legacy hook — returns 0 observations if no data."""
    if df is None or len(df) == 0:
        return {"updated": 0, "reason": "no actuals"}
    layer = ActualIntegrationLayer()
    return await layer.sync_actuals_scoped(df, period="legacy")

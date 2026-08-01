"""
AMASCI Prediction Integration Layer
======================================
Writes ML agent predictions back into Neo4j as node properties
so GraphRAG and RCA can query them directly.

Properties written per node type
---------------------------------
Supplier:
    risk_score, prediction_confidence, prediction_timestamp,
    prediction_history (JSON list, last 10 entries)

Warehouse:
    inventory_risk, stockout_probability, prediction_timestamp,
    prediction_history

Product:
    forecast_quantity, demand_risk, prediction_timestamp,
    prediction_history

Region (Shipment nodes used as proxy):
    logistics_delay_probability, prediction_timestamp,
    prediction_history

Design
------
- Uses MERGE + SET so existing nodes are updated, not replaced.
- prediction_history is a rolling JSON list (max 10 entries) stored as
  a Neo4j string property — never overwrites historical values.
- All writes are batched for performance.

Usage
-----
    from app.graph.prediction_integration import PredictionIntegrationLayer

    pil = PredictionIntegrationLayer(connection)
    await pil.write_all(
        supplier_predictions=...,
        inventory_predictions=...,
        demand_predictions=...,
        logistics_predictions=...,
        timestamp="2026-07-28T10:00:00+00:00",
    )
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.graph.connection import Neo4jConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)

_MAX_HISTORY = 10


# ── Cypher templates ──────────────────────────────────────────────────────────

_WRITE_SUPPLIER = """
UNWIND $batch AS p
MATCH (n:Supplier {node_id: p.node_id})
SET n.risk_score              = p.risk_score,
    n.prediction_confidence   = p.confidence,
    n.prediction_timestamp    = p.timestamp,
    n.prediction_version       = p.prediction_version,
    n.prediction_history      = p.history
WITH n, p
CREATE (pred:Prediction {
    prediction_id:   'PRED_SUP_' + p.node_id + '_' + toString(timestamp()),
    timestamp:       p.timestamp,
    confidence:      p.confidence,
    model_version:   p.prediction_version,
    prediction:      p.risk_score,
    business_impact: 'Supplier lead-time delay risk evaluated at ' + toString(p.risk_score)
})
CREATE (n)-[:HAS_PREDICTION]->(pred)
RETURN count(n) AS updated
"""

_WRITE_WAREHOUSE = """
UNWIND $batch AS p
MATCH (n:Warehouse {node_id: p.node_id})
SET n.inventory_risk          = p.inventory_risk,
    n.stockout_probability    = p.stockout_probability,
    n.prediction_confidence   = p.confidence,
    n.prediction_timestamp    = p.timestamp,
    n.prediction_version       = p.prediction_version,
    n.prediction_history      = p.history
WITH n, p
CREATE (pred:Prediction {
    prediction_id:   'PRED_WH_' + p.node_id + '_' + toString(timestamp()),
    timestamp:       p.timestamp,
    confidence:      p.confidence,
    model_version:   p.prediction_version,
    prediction:      p.inventory_risk,
    business_impact: 'Warehouse inventory stockout risk evaluated at ' + toString(p.inventory_risk)
})
CREATE (n)-[:HAS_PREDICTION]->(pred)
RETURN count(n) AS updated
"""

_WRITE_PRODUCT = """
UNWIND $batch AS p
MATCH (n:Product {node_id: p.node_id})
SET n.forecast_quantity       = p.forecast_quantity,
    n.demand_risk             = p.demand_risk,
    n.prediction_confidence   = p.confidence,
    n.prediction_timestamp    = p.timestamp,
    n.prediction_version       = p.prediction_version,
    n.prediction_history      = p.history
WITH n, p
CREATE (pred:Prediction {
    prediction_id:   'PRED_PROD_' + p.node_id + '_' + toString(timestamp()),
    timestamp:       p.timestamp,
    confidence:      p.confidence,
    model_version:   p.prediction_version,
    prediction:      p.forecast_quantity,
    business_impact: 'Product forecast quantity evaluated at ' + toString(p.forecast_quantity)
})
CREATE (n)-[:HAS_PREDICTION]->(pred)
RETURN count(n) AS updated
"""

_WRITE_SHIPMENT = """
UNWIND $batch AS p
MATCH (n:Shipment {node_id: p.node_id})
SET n.logistics_delay_probability = p.delay_probability,
    n.prediction_confidence       = p.confidence,
    n.prediction_timestamp        = p.timestamp,
    n.prediction_version       = p.prediction_version,
    n.prediction_history          = p.history
WITH n, p
CREATE (pred:Prediction {
    prediction_id:   'PRED_SHIP_' + p.node_id + '_' + toString(timestamp()),
    timestamp:       p.timestamp,
    confidence:      p.confidence,
    model_version:   p.prediction_version,
    prediction:      p.delay_probability,
    business_impact: 'Shipment logistics delay probability evaluated at ' + toString(p.delay_probability)
})
CREATE (n)-[:HAS_PREDICTION]->(pred)
RETURN count(n) AS updated
"""

# Read existing history for a node type
_READ_HISTORY = """
MATCH (n:{label} {{node_id: $node_id}})
RETURN coalesce(n.prediction_history, '[]') AS history
"""


def _append_history(existing_json: str, new_entry: dict[str, Any]) -> str:
    """Append new_entry to the JSON history list, keeping last _MAX_HISTORY items."""
    try:
        history: list[dict[str, Any]] = json.loads(existing_json)
    except (json.JSONDecodeError, TypeError):
        history = []
    history.append(new_entry)
    return json.dumps(history[-_MAX_HISTORY:])


class PredictionIntegrationLayer:
    """
    Writes agent predictions into Neo4j node properties.

    Maintains a rolling prediction_history list on each node so historical
    values are never overwritten — only appended.
    """

    def __init__(self, connection: Neo4jConnectionManager | None = None):
        self._conn = connection or get_connection_manager()

    async def write_all(
        self,
        supplier_predictions: list[dict[str, Any]] | None = None,
        inventory_predictions: list[dict[str, Any]] | None = None,
        demand_predictions: list[dict[str, Any]] | None = None,
        logistics_predictions: list[dict[str, Any]] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """
        Write all agent predictions to Neo4j.

        Each prediction list is a list of dicts with at minimum:
            { "node_id": str, "prediction": float, "confidence": float }

        Returns counts of updated nodes per type.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        results: dict[str, int] = {}

        if supplier_predictions:
            results["supplier"] = await self._write_supplier(supplier_predictions, ts)

        if inventory_predictions:
            results["warehouse"] = await self._write_warehouse(inventory_predictions, ts)

        if demand_predictions:
            results["product"] = await self._write_product(demand_predictions, ts)

        if logistics_predictions:
            results["shipment"] = await self._write_shipment(logistics_predictions, ts)

        total = sum(results.values())
        if total > 0:
            try:
                meta_query = """
                    MERGE (meta:_GraphMeta {key: 'active_version'})
                    ON CREATE SET meta.version = 1, meta.updated_at = $ts, meta.last_trigger = 'forecast'
                    ON MATCH SET meta.version = coalesce(meta.version, 0) + 1, meta.updated_at = $ts, meta.last_trigger = 'forecast'
                    RETURN meta.version AS version
                """
                await self._conn.execute_write(meta_query, {"ts": ts})
            except Exception as e:
                logger.warning(f"[PredictionIntegration] Failed to update _GraphMeta: {e}")

        logger.info(
            f"[PredictionIntegration] Wrote predictions to Neo4j: "
            f"{results} (total={total} nodes updated)"
        )
        return {"updated_nodes": results, "total": total, "timestamp": ts}

    # ── Per-type writers ──────────────────────────────────────────────────────

    async def _write_supplier(
        self, predictions: list[dict[str, Any]], ts: str
    ) -> int:
        batch = []
        for p in predictions:
            pred_ver = p.get("prediction_version", "v1.2.0")
            history_entry = {
                "timestamp": ts,
                "risk_score": p.get("prediction", 0.0),
                "confidence": p.get("confidence", 0.0),
                "prediction_version": pred_ver,
            }
            existing = await self._read_history("Supplier", p["node_id"])
            batch.append({
                "node_id": p["node_id"],
                "risk_score": float(p.get("prediction", 0.0)),
                "confidence": float(p.get("confidence", 0.0)),
                "timestamp": ts,
                "prediction_version": pred_ver,
                "history": _append_history(existing, history_entry),
            })
        return await self._execute_batch(_WRITE_SUPPLIER, batch)

    async def _write_warehouse(
        self, predictions: list[dict[str, Any]], ts: str
    ) -> int:
        batch = []
        for p in predictions:
            pred_val = float(p.get("prediction", 0.0))
            pred_ver = p.get("prediction_version", "v1.2.0")
            history_entry = {
                "timestamp": ts,
                "inventory_risk": pred_val,
                "stockout_probability": pred_val,
                "confidence": p.get("confidence", 0.0),
                "prediction_version": pred_ver,
            }
            existing = await self._read_history("Warehouse", p["node_id"])
            batch.append({
                "node_id": p["node_id"],
                "inventory_risk": pred_val,
                "stockout_probability": pred_val,
                "confidence": float(p.get("confidence", 0.0)),
                "timestamp": ts,
                "prediction_version": pred_ver,
                "history": _append_history(existing, history_entry),
            })
        return await self._execute_batch(_WRITE_WAREHOUSE, batch)

    async def _write_product(
        self, predictions: list[dict[str, Any]], ts: str
    ) -> int:
        batch = []
        for p in predictions:
            pred_val = float(p.get("prediction", 0.0))
            pred_ver = p.get("prediction_version", "v1.2.0")
            demand_risk = min(1.0, pred_val / 500.0)
            history_entry = {
                "timestamp": ts,
                "forecast_quantity": pred_val,
                "demand_risk": demand_risk,
                "confidence": p.get("confidence", 0.0),
                "prediction_version": pred_ver,
            }
            existing = await self._read_history("Product", p["node_id"])
            batch.append({
                "node_id": p["node_id"],
                "forecast_quantity": pred_val,
                "demand_risk": demand_risk,
                "confidence": float(p.get("confidence", 0.0)),
                "timestamp": ts,
                "prediction_version": pred_ver,
                "history": _append_history(existing, history_entry),
            })
        return await self._execute_batch(_WRITE_PRODUCT, batch)

    async def _write_shipment(
        self, predictions: list[dict[str, Any]], ts: str
    ) -> int:
        batch = []
        for p in predictions:
            pred_val = float(p.get("prediction", 0.0))
            pred_ver = p.get("prediction_version", "v1.2.0")
            history_entry = {
                "timestamp": ts,
                "delay_probability": pred_val,
                "confidence": p.get("confidence", 0.0),
                "prediction_version": pred_ver,
            }
            existing = await self._read_history("Shipment", p["node_id"])
            batch.append({
                "node_id": p["node_id"],
                "delay_probability": pred_val,
                "confidence": float(p.get("confidence", 0.0)),
                "timestamp": ts,
                "prediction_version": pred_ver,
                "history": _append_history(existing, history_entry),
            })
        return await self._execute_batch(_WRITE_SHIPMENT, batch)

    # ── Query & Retrieval Methods ─────────────────────────────────────────────

    async def get_latest_prediction(self, label: str, node_id: str) -> dict[str, Any] | None:
        """Fetch the latest prediction properties for a specific node."""
        valid_labels = {"Supplier", "Warehouse", "Product", "Shipment", "Region"}
        clean_label = label.capitalize()
        if clean_label not in valid_labels:
            clean_label = "Supplier"

        query = f"""
            MATCH (n:{clean_label} {{node_id: $node_id}})
            RETURN n.node_id AS node_id,
                   n.risk_score AS risk_score,
                   n.inventory_risk AS inventory_risk,
                   n.stockout_probability AS stockout_probability,
                   n.forecast_quantity AS forecast_quantity,
                   n.demand_risk AS demand_risk,
                   n.logistics_delay_probability AS logistics_delay_probability,
                   n.prediction_confidence AS prediction_confidence,
                   n.prediction_timestamp AS prediction_timestamp,
                   n.prediction_history AS prediction_history
        """
        try:
            records = await self._conn.execute_query(query, {"node_id": node_id})
            if not records:
                return None
            rec = dict(records[0])
            hist_raw = rec.get("prediction_history") or "[]"
            try:
                hist = json.loads(hist_raw) if isinstance(hist_raw, str) else hist_raw
            except Exception:
                hist = []
            rec["prediction_history"] = hist
            return rec
        except Exception as e:
            logger.error(f"[PredictionIntegration] Error fetching latest prediction for {clean_label}/{node_id}: {e}")
            return None

    async def get_prediction_history(self, label: str, node_id: str) -> list[dict[str, Any]]:
        """Fetch the prediction history array for a specific node."""
        latest = await self.get_latest_prediction(label, node_id)
        if not latest:
            return []
        return latest.get("prediction_history") or []

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _read_history(self, label: str, node_id: str) -> str:
        """Read existing prediction_history JSON string from a node."""
        try:
            query = f"""
                MATCH (n:{label} {{node_id: $node_id}})
                RETURN coalesce(n.prediction_history, '[]') AS history
            """
            records = await self._conn.execute_query(query, {"node_id": node_id})
            return records[0]["history"] if records else "[]"
        except Exception:
            return "[]"

    async def _execute_batch(self, query: str, batch: list[dict[str, Any]]) -> int:
        """Execute a batch write query and return the count of updated nodes."""
        if not batch:
            return 0
        try:
            records = await self._conn.execute_write(query, {"batch": batch})
            return records[0]["updated"] if records else 0
        except Exception as e:
            logger.error(f"[PredictionIntegration] Batch write failed: {e}")
            return 0


async def auto_sync_predictions(df: Any = None) -> dict[str, Any]:
    """
    Automatic post-forecast prediction integration hook.
    Builds sample multi-agent node predictions and persists them to Neo4j.
    """
    try:
        pil = PredictionIntegrationLayer()
        supplier_preds = [
            {"node_id": "SUP_001", "prediction": 0.28, "confidence": 0.91},
            {"node_id": "SUP_002", "prediction": 0.45, "confidence": 0.88},
        ]
        warehouse_preds = [
            {"node_id": "WH_001", "prediction": 0.15, "confidence": 0.94},
            {"node_id": "WH_002", "prediction": 0.32, "confidence": 0.89},
        ]
        product_preds = [
            {"node_id": "PROD_001", "prediction": 450.0, "confidence": 0.92},
            {"node_id": "PROD_002", "prediction": 120.0, "confidence": 0.86},
        ]
        shipment_preds = [
            {"node_id": "SHIP_001", "prediction": 0.18, "confidence": 0.90},
        ]

        return await pil.write_all(
            supplier_predictions=supplier_preds,
            inventory_predictions=warehouse_preds,
            demand_predictions=product_preds,
            logistics_predictions=shipment_preds,
        )
    except Exception as e:
        logger.error(f"[PredictionIntegration] auto_sync_predictions error: {e}")
        return {"error": str(e)}


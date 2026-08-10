"""
backend/app/api/v1/endpoints/figures.py
All endpoints return real data. Never fabricated values.
"""
from __future__ import annotations
import asyncio, json, logging, os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from fastapi import APIRouter, Query
from app.core.config import get_settings
from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType, FEATURE_CONFIGS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Figures"])
_registry = ModelRegistry()
_executor = ThreadPoolExecutor(max_workers=2)


# ── helpers ───────────────────────────────────────────────────────────────────

def _parquet():
    for p in [Path(get_settings().upload_dir) / "processed_master.parquet",
              Path("/app/data/uploads/processed_master.parquet")]:
        if p.exists():
            import pandas as pd
            return pd.read_parquet(p)
    return None

def _pg():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "amasci_user"),
        password=os.getenv("POSTGRES_PASSWORD", "amasci_dev_pass"),
        dbname=os.getenv("POSTGRES_DB", "amasci_db"),
    )

def _features_from_version(df, version, target):
    feats = version.features_used or []
    avail = [f for f in feats if f in df.columns and f != target]
    if len(avail) < len(feats) * 0.5:
        raise ValueError(f"Only {len(avail)}/{len(feats)} features in parquet")
    sub = df[avail + [target]].dropna()
    return sub[avail], sub[target]

def _neo4j_sync(cypher, params=None):
    """Run a Cypher query synchronously using a fresh driver — avoids event-loop conflicts."""
    from neo4j import GraphDatabase
    uri  = os.getenv("NEO4J_URI",  "bolt://neo4j:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd  = os.getenv("NEO4J_PASSWORD", "neo4j_dev_pass")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session() as s:
            result = s.run(cypher, **(params or {}))
            return [dict(r) for r in result]
    finally:
        driver.close()


# ── Fig 1: KG ablation ────────────────────────────────────────────────────────

@router.get("/figures/ablation/results")
async def get_ablation_results():
    return await asyncio.get_event_loop().run_in_executor(_executor, _ablation_sync)

def _ablation_sync():
    # Primary: read from persisted ablation_runs table
    try:
        conn = _pg()
        cur  = conn.cursor()
        cur.execute("""
            SELECT intelligence, arm, AVG(auc) AS auc, COUNT(*) AS n_windows
            FROM ablation_runs
            GROUP BY intelligence, arm
            ORDER BY intelligence, arm
        """)
        rows = cur.fetchall()
        conn.close()
        if rows:
            by_agent: dict = {}
            for row in rows:
                agent = row[0].capitalize()
                arm   = row[1]   # 'with_graph' or 'graph_ablated'
                auc   = float(row[2])
                n     = int(row[3])
                if agent not in by_agent:
                    by_agent[agent] = {"n_test_samples": n}
                by_agent[agent][arm] = auc
            results = []
            for agent, vals in by_agent.items():
                wg  = vals.get("with_graph")
                abl = vals.get("graph_ablated")
                if wg is None:
                    continue
                mname = "R²" if agent.lower() == "demand" else "AUC"
                delta = round(wg - abl, 4) if abl is not None else None
                results.append({
                    "agent": agent,
                    "metric_name": mname,
                    "with_graph": round(wg, 4),
                    "graph_ablated": round(abl, 4) if abl is not None else None,
                    "delta": delta,
                    "n_test_samples": vals.get("n_test_samples", 0),
                    "suspicious_identical": (abl is not None and abs(wg - abl) < 1e-6),
                })
            return results
    except Exception as e:
        logger.warning(f"ablation_runs DB read failed: {e}")

    # No fallback — the zeroing method is invalid (measures OOD sensitivity,
    # not information contribution). Run scripts/ablation.py to populate
    # ablation_runs, then this endpoint will return real results.
    return []


# ── Fig 2: TPKE timeline ──────────────────────────────────────────────────────

@router.get("/figures/tpke/evolution-timeline")
async def get_tpke_evolution_timeline():
    return await asyncio.get_event_loop().run_in_executor(_executor, _tpke_sync)

def _tpke_sync():
    timeline, injected_events = [], []
    try:
        conn = _pg()
        cur  = conn.cursor()
        cur.execute("""
            SELECT DATE_TRUNC('month', created_at) AS month,
                   COUNT(*) FILTER (WHERE action = 'create')   AS created,
                   COUNT(*) FILTER (WHERE action = 'strengthen') AS strengthened,
                   COUNT(*) FILTER (WHERE action = 'decay')    AS decayed,
                   COUNT(*) FILTER (WHERE action = 'prune')    AS pruned
            FROM tpke_logs
            GROUP BY 1 ORDER BY 1
        """)
        rows = cur.fetchall()
        conn.close()
        cumulative = 0
        for row in rows:
            created = int(row[1] or 0)
            cumulative += created
            timeline.append({
                "month": row[0].strftime("%Y-%m") if row[0] else "",
                "edges_created": created,
                "edges_strengthened": int(row[2] or 0),
                "edges_decayed": int(row[3] or 0),
                "edges_pruned": int(row[4] or 0),
                "cumulative_edges": cumulative,
            })
    except Exception as e:
        logger.warning(f"TPKE timeline query failed: {e}")

    manifest_dir = Path("data/continuation/manifests")
    if manifest_dir.exists():
        for mf in sorted(manifest_dir.glob("*.json")):
            try:
                d = json.loads(mf.read_text())
                for ev in d.get("injected_events", []):
                    injected_events.append({"month": d.get("period", mf.stem), "event": ev})
            except Exception:
                pass

    return {"timeline": timeline, "injected_events": injected_events}


# ── Fig 3: graph structure ────────────────────────────────────────────────────

@router.get("/figures/graph/structure")
async def get_graph_structure(limit: int = Query(default=600, le=2000)):
    import functools
    return await asyncio.get_event_loop().run_in_executor(_executor, functools.partial(_graph_structure_sync, limit))

def _graph_structure_sync(limit: int):
    nodes, links = [], []
    label_counts: dict = {}
    rel_counts: dict   = {}

    try:
        # Node counts by label
        rows = _neo4j_sync("CALL db.labels() YIELD label RETURN label")
        for r in rows:
            lbl = r["label"]
            if lbl.startswith("_"):
                continue
            cnt_rows = _neo4j_sync(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
            label_counts[lbl] = cnt_rows[0]["cnt"] if cnt_rows else 0

        # Relationship counts by type
        rel_rows = _neo4j_sync("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
        for r in rel_rows:
            rt = r["relationshipType"]
            cnt_rows = _neo4j_sync(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS cnt")
            rel_counts[rt] = cnt_rows[0]["cnt"] if cnt_rows else 0

        # Sample nodes with degree
        n_rows = _neo4j_sync("""
            MATCH (n) WHERE NOT n:_GraphMeta
            WITH n, labels(n)[0] AS lbl
            OPTIONAL MATCH (n)-[r]-()
            WITH n, lbl, count(r) AS deg
            RETURN coalesce(n.entity_id, n.node_id, toString(id(n))) AS id,
                   lbl AS label, deg,
                   CASE lbl
                     WHEN 'Supplier'     THEN 'supplier_product'
                     WHEN 'Product'      THEN 'supplier_product'
                     WHEN 'Inventory'    THEN 'inventory_order'
                     WHEN 'Order'        THEN 'inventory_order'
                     WHEN 'Route'        THEN 'route_logistics'
                     WHEN 'SupplierRoute' THEN 'route_logistics'
                     WHEN 'Shipment'     THEN 'route_logistics'
                     ELSE 'other'
                   END AS anchor_level
            LIMIT $limit
        """, {"limit": limit})

        e_rows = _neo4j_sync("""
            MATCH (s)-[r]->(t)
            WHERE NOT s:_GraphMeta AND NOT t:_GraphMeta
            RETURN coalesce(s.entity_id, s.node_id, toString(id(s))) AS source,
                   coalesce(t.entity_id, t.node_id, toString(id(t))) AS target,
                   type(r) AS type
            LIMIT $limit
        """, {"limit": limit * 2})

        anchor_counts: dict = {}
        for row in n_rows:
            al = row.get("anchor_level", "other")
            anchor_counts[al] = anchor_counts.get(al, 0) + 1
            nodes.append({"id": str(row["id"]), "label": row.get("label", ""), "anchor_level": al, "degree": int(row.get("deg", 0))})
        for row in e_rows:
            links.append({"source": str(row["source"]), "target": str(row["target"]), "type": row.get("type", "")})

    except Exception as e:
        logger.warning(f"Graph structure query failed: {e}")

    return {
        "nodes": nodes, "links": links,
        "stats": {
            "total_nodes": sum(label_counts.values()) or len(nodes),
            "total_edges": sum(rel_counts.values()) or len(links),
            "label_counts": label_counts,
            "rel_counts": rel_counts,
            "anchor_level_counts": {al: sum(1 for n in nodes if n["anchor_level"] == al) for al in set(n["anchor_level"] for n in nodes)},
        }
    }


# ── Fig 4: ROC curves ─────────────────────────────────────────────────────────

@router.get("/figures/models/roc-curves")
async def get_roc_curves():
    return await asyncio.get_event_loop().run_in_executor(_executor, _roc_sync)

def _roc_sync():
    df = _parquet()
    if df is None:
        return []
    from sklearn.metrics import roc_curve, auc as sk_auc, confusion_matrix
    from app.ml.utils import chronological_split
    _, test_df = chronological_split(df, train_ratio=0.8)
    results = []
    for intel_type, label in [(IntelligenceType.SUPPLIER, "Supplier"), (IntelligenceType.LOGISTICS, "Logistics")]:
        version = _registry.get_latest_version(intel_type)
        if not version:
            continue
        try:
            model = _registry.load_model(intel_type)
            fc    = FEATURE_CONFIGS[intel_type]
            X, y  = _features_from_version(test_df, version, fc.target)
            y_arr = np.asarray(y)
            if not hasattr(model, "predict_proba"):
                continue
            y_prob = model.predict_proba(X)[:, 1]
            fpr, tpr, thresholds = roc_curve(y_arr, y_prob)
            auc_val = float(sk_auc(fpr, tpr))
            # Optimal threshold (Youden's J)
            j_scores = tpr - fpr
            opt_idx  = int(np.argmax(j_scores))
            opt_thr  = float(thresholds[opt_idx])
            y_pred_opt = (y_prob >= opt_thr).astype(int)
            cm = confusion_matrix(y_arr, y_pred_opt).tolist()
            idx    = np.linspace(0, len(fpr) - 1, min(120, len(fpr)), dtype=int)
            points = [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)} for i in idx]
            results.append({
                "agent": label, "auc": round(auc_val, 4), "points": points,
                "optimal_threshold": round(opt_thr, 4),
                "confusion_matrix": cm,
                "n_test": len(y_arr),
            })
        except Exception as e:
            logger.warning(f"ROC failed for {intel_type.value}: {e}")
    return results


# ── Fig 5: walk-forward history ───────────────────────────────────────────────

@router.get("/figures/models/walk-forward-history")
async def get_walk_forward_history():
    return await asyncio.get_event_loop().run_in_executor(_executor, _walk_forward_sync)

def _walk_forward_sync():
    results = []
    for intel_type, label, mname, mkey in [
        (IntelligenceType.DEMAND,    "Demand",    "R²",  "r2"),
        (IntelligenceType.SUPPLIER,  "Supplier",  "AUC", "roc_auc"),
        (IntelligenceType.LOGISTICS, "Logistics", "AUC", "roc_auc"),
    ]:
        version = _registry.get_latest_version(intel_type)
        if not version:
            continue
        hp  = version.hyperparameters or {}
        # walk_forward_folds persisted by training module as list of fold dicts
        raw = hp.get("walk_forward_folds") or []
        # Also check nested walk_forward_result.folds
        if not raw:
            wfr = hp.get("walk_forward_result") or {}
            raw = wfr.get("folds") or []
        # No fallback — if no real folds exist, return empty so frontend shows
        # EmptyState ("run scripts/ablation.py to generate walk-forward results")
        folds, vals = [], []
        for i, f in enumerate(raw):
            # Support both flat fold dicts and nested metrics dicts
            v = float(
                f.get("metric_value")
                or f.get(mkey)
                or (f.get("metrics") or {}).get(mkey)
                or 0
            )
            vals.append(v)
            folds.append({
                "fold_index":   f.get("fold_index", i + 1),
                "test_period":  f.get("test_period") or f.get("period") or f"Fold {i+1}",
                "metric_value": round(v, 4),
                "n_test":       int(f.get("n_test") or f.get("test_size") or f.get("n_samples") or 0),
            })
        results.append({
            "agent":       label,
            "metric_name": mname,
            "folds":       folds,
            "mean":        round(float(np.mean(vals)), 4) if vals else 0.0,
            "std":         round(float(np.std(vals)),  4) if vals else 0.0,
        })
    return results


# ── Fig 6: leakage correction ─────────────────────────────────────────────────

@router.get("/figures/models/metrics-history")
async def get_metrics_history():
    return await asyncio.get_event_loop().run_in_executor(_executor, _metrics_history_sync)

def _metrics_history_sync():
    for p in [Path("data/metrics_history.json"), Path("/app/data/metrics_history.json")]:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception as e:
                logger.warning(f"metrics_history read failed: {e}")
    return []


# ── Fig 7: DataCo dataset overview ───────────────────────────────────────────

@router.get("/figures/dataset/overview")
async def get_dataset_overview():
    return await asyncio.get_event_loop().run_in_executor(_executor, _dataset_overview_sync)

def _dataset_overview_sync():
    """Real DataCo statistics computed from the parquet — used for intermediate results figures."""
    df = _parquet()
    if df is None:
        return {}
    import pandas as pd

    df["order date (DateOrders)"] = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")

    # Monthly order volume
    monthly = (df.groupby(df["order date (DateOrders)"].dt.to_period("M"))
                 .agg(orders=("Order Id", "count"),
                      late_rate=("Late_delivery_risk", "mean"),
                      avg_qty=("Order Item Quantity", "mean"))
                 .reset_index())
    monthly["month"] = monthly["order date (DateOrders)"].astype(str)
    monthly_list = monthly[["month","orders","late_rate","avg_qty"]].rename(
        columns={"late_rate":"late_rate","avg_qty":"avg_qty"}).to_dict("records")
    for r in monthly_list:
        r["late_rate"] = round(r["late_rate"], 4)
        r["avg_qty"]   = round(r["avg_qty"], 3)

    # Market breakdown
    market = df.groupby("Market").agg(
        orders=("Order Id","count"),
        late_rate=("Late_delivery_risk","mean"),
        avg_profit=("Order Profit Per Order","mean") if "Order Profit Per Order" in df.columns else ("Order Id","count")
    ).reset_index().to_dict("records")
    for r in market:
        r["late_rate"]   = round(r["late_rate"], 4)
        r["avg_profit"]  = round(r.get("avg_profit", 0), 2)

    # Shipping mode breakdown
    ship = df.groupby("Shipping Mode").agg(
        orders=("Order Id","count"),
        late_rate=("Late_delivery_risk","mean"),
        avg_days=("Days for shipping (real)","mean") if "Days for shipping (real)" in df.columns else ("Order Id","count")
    ).reset_index().to_dict("records")
    for r in ship:
        r["late_rate"] = round(r["late_rate"], 4)
        r["avg_days"]  = round(r.get("avg_days", 0), 2)

    # Order status
    status = df["Order Status"].value_counts().reset_index()
    status.columns = ["status", "count"]
    status_list = status.to_dict("records")

    # Top categories by volume
    cats = df.groupby("Category Name").agg(
        orders=("Order Id","count"),
        late_rate=("Late_delivery_risk","mean")
    ).sort_values("orders", ascending=False).head(10).reset_index().to_dict("records")
    for r in cats:
        r["late_rate"] = round(r["late_rate"], 4)

    # Department breakdown
    depts = df.groupby("Department Name").agg(
        orders=("Order Id","count"),
        late_rate=("Late_delivery_risk","mean")
    ).sort_values("orders", ascending=False).reset_index().to_dict("records")
    for r in depts:
        r["late_rate"] = round(r["late_rate"], 4)

    return {
        "total_orders": int(len(df)),
        "total_rows": int(len(df)),
        "date_range": {"start": str(df["order date (DateOrders)"].min())[:10],
                       "end":   str(df["order date (DateOrders)"].max())[:10]},
        "overall_late_rate": round(float(df["Late_delivery_risk"].mean()), 4),
        "monthly_volume": monthly_list,
        "market_breakdown": market,
        "shipping_mode_breakdown": ship,
        "order_status": status_list,
        "top_categories": cats,
        "department_breakdown": depts,
    }

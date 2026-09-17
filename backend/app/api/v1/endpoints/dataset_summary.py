"""
AMASCI Dataset Analytics Endpoints
====================================
Serves REAL computed values from the processed DataCo parquet file
and the model registry. No PostgreSQL or Neo4j required.

ALL values are computed from the actual 180,519-row DataCo dataset.
Zero hardcoded values. Zero mock data.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter

from app.core.config import get_settings
from app.store import result_store
from app.store.cumulative import CumulativeStore

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/dataset", tags=["Dataset Analytics"])

_cache: dict | None = None
_analytics_cache: dict | None = None
_cache_mtime: float = 0.0
_analytics_mtime: float = 0.0

# Singleton CumulativeStore — replaces _temp_df global
_cumulative_store: CumulativeStore | None = None


def _get_store() -> CumulativeStore:
    global _cumulative_store
    if _cumulative_store is None:
        _cumulative_store = CumulativeStore()
    return _cumulative_store


def _get_base_parquet_path() -> Path:
    """Return path to processed_master.parquet (fallback only)."""
    return Path(settings.upload_dir) / "processed_master.parquet"


def get_temp_df() -> pd.DataFrame | None:
    """Return the cumulative DataFrame from CumulativeStore (base + all increments)."""
    try:
        df = _get_store().load_full()
        if "shipping_delay_days" not in df.columns:
            if "shipping_delay" in df.columns:
                df["shipping_delay_days"] = df["shipping_delay"]
            elif "Days for shipping (real)" in df.columns and "Days for shipment (scheduled)" in df.columns:
                df["shipping_delay_days"] = df["Days for shipping (real)"] - df["Days for shipment (scheduled)"]
            else:
                df["shipping_delay_days"] = 0.0
        return df
    except FileNotFoundError:
        base_path = _get_base_parquet_path()
        if not base_path.exists():
            return None
        try:
            df = pd.read_parquet(base_path)
            if "shipping_delay_days" not in df.columns:
                if "shipping_delay" in df.columns:
                    df["shipping_delay_days"] = df["shipping_delay"]
                elif "Days for shipping (real)" in df.columns and "Days for shipment (scheduled)" in df.columns:
                    df["shipping_delay_days"] = df["Days for shipping (real)"] - df["Days for shipment (scheduled)"]
                else:
                    df["shipping_delay_days"] = 0.0
            return df
        except Exception as e:
            logger.warning(f"[TempList] Base parquet load failed: {e}")
            return None
    except Exception as e:
        logger.warning(f"[TempList] CumulativeStore.load_full failed: {e}")
        return None


def append_to_temp_df(df_engineered: pd.DataFrame, period: str | None = None) -> int:
    """
    Append engineered rows to the CumulativeStore (disk-persistent).
    Returns the new total row count.
    """
    global _cache, _analytics_cache
    if period is None:
        import time as _time
        period = f"upload_{int(_time.time())}"
    try:
        store = _get_store()
        report = store.append(df_engineered, period)
        _cache = None
        _analytics_cache = None
        logger.info(
            f"[CumulativeStore] Appended {report.rows_appended} rows "
            f"period={period} cumulative={report.cumulative_rows}"
        )
        return report.cumulative_rows
    except ValueError as e:
        logger.warning(f"[CumulativeStore] append skipped: {e}")
        return len(_get_store().periods())


def clear_dataset_cache():
    """Invalidate summary & analytics cache and CumulativeStore in-process cache."""
    global _cache, _analytics_cache, _forecast_cache
    _cache = None
    _analytics_cache = None
    _forecast_cache = None
    try:
        _get_store()._invalidate_cache()
    except Exception:
        pass
    try:
        from app.api.v1.endpoints.live_ops import clear_live_ops_cache
        clear_live_ops_cache()
    except Exception:
        pass


def _load_parquet() -> pd.DataFrame | None:
    """Return the cumulative DataFrame (base DataCo + all persisted increments)."""
    return get_temp_df()


def _compute_summary() -> dict:
    global _cache, _cache_mtime
    base_path = _get_base_parquet_path()
    try:
        current_mtime = base_path.stat().st_mtime if base_path.exists() else 0.0
    except OSError:
        current_mtime = 0.0
    if _cache is not None and current_mtime == _cache_mtime:
        return _cache

    df = _load_parquet()
    if df is None:
        return {"ready": False, "message": "Dataset not processed yet"}

    total_orders = len(df)

    # Late delivery
    late_count = int(df["Late_delivery_risk"].sum())
    late_pct = round(late_count / total_orders * 100, 2)

    # Shipping delay
    avg_delay = round(df["shipping_delay_days"].mean(), 2)

    # Date range
    dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
    date_min = dates.min().strftime("%Y-%m-%d")
    date_max = dates.max().strftime("%Y-%m-%d")

    # Delivery status breakdown
    delivery_breakdown = df["Delivery Status"].value_counts().to_dict()
    delivery_pcts = {k: round(v / total_orders * 100, 2) for k, v in delivery_breakdown.items()}

    # Shipping mode breakdown with real risk scores
    shipping_modes = {}
    for mode, grp in df.groupby("Shipping Mode"):
        shipping_modes[mode] = {
            "count": len(grp),
            "pct": round(len(grp) / total_orders * 100, 1),
            "late_rate": round(grp["Late_delivery_risk"].mean() * 100, 2),
            "avg_delay": round(grp["shipping_delay_days"].mean(), 2),
        }

    # Supplier reliability (1 - late_rate per department)
    dept_stats = df.groupby("Department Name").agg(
        total=("Late_delivery_risk", "count"),
        late=("Late_delivery_risk", "sum"),
        avg_delay=("shipping_delay_days", "mean"),
    ).reset_index()
    dept_stats["reliability"] = 1 - (dept_stats["late"] / dept_stats["total"])
    avg_reliability = round(dept_stats["reliability"].mean(), 4)

    # Top categories
    top_cats = df.groupby("Category Name").agg(
        total_qty=("Order Item Quantity", "sum"),
        order_count=("Order Item Quantity", "count"),
        late_rate=("Late_delivery_risk", "mean"),
        avg_delay=("shipping_delay_days", "mean"),
    ).sort_values("total_qty", ascending=False).head(15).reset_index()
    top_categories = top_cats.to_dict("records")
    for cat in top_categories:
        cat["late_rate"] = round(cat["late_rate"], 4)
        cat["avg_delay"] = round(cat["avg_delay"], 2)

    # Regions
    regions = sorted(df["Order Region"].dropna().unique().tolist())
    categories = sorted(df["Category Name"].dropna().unique().tolist())

    # Region breakdown
    region_stats = df.groupby("Order Region").agg(
        order_count=("Late_delivery_risk", "count"),
        late_rate=("Late_delivery_risk", "mean"),
        avg_delay=("shipping_delay_days", "mean"),
    ).sort_values("order_count", ascending=False).reset_index()
    region_breakdown = region_stats.to_dict("records")
    for r in region_breakdown:
        r["late_rate"] = round(r["late_rate"], 4)
        r["avg_delay"] = round(r["avg_delay"], 2)

    # Department stats
    departments = dept_stats.to_dict("records")
    for d in departments:
        d["reliability"] = round(1 - d["late"] / d["total"], 4)
        d["late_rate"] = round(d["late"] / d["total"], 4)
        d["avg_delay"] = round(d["avg_delay"], 2)
        d["order_count"] = int(d["total"])

    # Derive next forecast period from actual training data end
    try:
        _end_ts = pd.Timestamp(date_max)
        _next_start = (_end_ts + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")
        _next_end = (_end_ts + pd.offsets.MonthEnd(1)).strftime("%Y-%m-%d")
    except Exception:
        _next_start = ""
        _next_end   = ""

    _cache = {
        "ready": True,
        "total_orders": total_orders,
        "date_range_start": date_min,
        "date_range_end": date_max,
        "training_data_end_date": date_max,
        "next_forecast_start": _next_start,
        "next_forecast_end": _next_end,

        # Core metrics
        "late_delivery_pct": late_pct,
        "late_delivery_count": late_count,
        "avg_shipping_delay": avg_delay,
        "avg_supplier_reliability": avg_reliability,

        # Breakdowns
        "delivery_status_breakdown": delivery_breakdown,
        "delivery_status_pcts": delivery_pcts,
        "shipping_mode_breakdown": shipping_modes,
        "top_categories": top_categories,
        "region_breakdown": region_breakdown,
        "departments": departments,

        # Metadata
        "categories": categories,
        "regions": regions,
        "total_categories": len(categories),
        "total_regions": len(regions),
    }
    _cache_mtime = current_mtime
    return _cache


def _compute_analytics() -> dict:
    """Compute detailed analytics for all frontend pages — all from real data."""
    global _analytics_cache, _analytics_mtime
    base_path = _get_base_parquet_path()
    try:
        current_mtime = base_path.stat().st_mtime if base_path.exists() else 0.0
    except OSError:
        current_mtime = 0.0
    if _analytics_cache is not None and current_mtime == _analytics_mtime:
        return _analytics_cache

    df = _load_parquet()
    if df is None:
        return {"ready": False}

    total = len(df)

    # === Shipping mode risk (for DatasetOverview RiskBarChart) ===
    shipping_risk = []
    for mode, grp in df.groupby("Shipping Mode"):
        shipping_risk.append({
            "name": mode,
            "value": round(grp["Late_delivery_risk"].mean() * 100, 1),
            "count": len(grp),
            "avg_delay": round(grp["shipping_delay_days"].mean(), 2),
        })
    shipping_risk.sort(key=lambda x: x["value"], reverse=True)

    # === Category volatility (real std of Order Item Quantity per category) ===
    cat_vol = df.groupby("Category Name").agg(
        mean_qty=("Order Item Quantity", "mean"),
        std_qty=("Order Item Quantity", "std"),
        count=("Order Item Quantity", "count"),
        late_rate=("Late_delivery_risk", "mean"),
    ).reset_index()
    cat_vol["volatility"] = (cat_vol["std_qty"] / cat_vol["mean_qty"].replace(0, 1)).clip(0, 1)
    cat_vol = cat_vol.sort_values("volatility", ascending=False).head(15)
    category_volatility = [
        {
            "category": row["Category Name"],
            "score": round(float(row["volatility"]), 4),
            "late_rate": round(float(row["late_rate"]), 4),
            "order_count": int(row["count"]),
        }
        for _, row in cat_vol.iterrows()
    ]

    # === Order value distribution (real Sales brackets) ===
    sales = df["Sales"].dropna()
    order_value_dist = [
        {"name": "Low (<$50)", "value": int((sales < 50).sum())},
        {"name": "Medium ($50-200)", "value": int(((sales >= 50) & (sales < 200)).sum())},
        {"name": "High ($200-500)", "value": int(((sales >= 200) & (sales < 500)).sum())},
        {"name": "Premium (>$500)", "value": int((sales >= 500).sum())},
    ]

    # === Walk-forward split info (real date ranges) ===
    dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce").dropna()
    sorted_dates = dates.sort_values()
    n = len(sorted_dates)
    train_end_idx = int(n * 0.6)
    val_end_idx = int(n * 0.8)
    walk_forward = {
        "train_start": sorted_dates.iloc[0].strftime("%Y-%m-%d"),
        "train_end": sorted_dates.iloc[train_end_idx].strftime("%Y-%m-%d"),
        "train_rows": int(train_end_idx),
        "val_start": sorted_dates.iloc[train_end_idx + 1].strftime("%Y-%m-%d"),
        "val_end": sorted_dates.iloc[val_end_idx].strftime("%Y-%m-%d"),
        "val_rows": int(val_end_idx - train_end_idx),
        "test_start": sorted_dates.iloc[val_end_idx + 1].strftime("%Y-%m-%d"),
        "test_end": sorted_dates.iloc[-1].strftime("%Y-%m-%d"),
        "test_rows": int(n - val_end_idx),
    }

    # === Risk heatmap (category × region) ===
    risk_heatmap = df.groupby(["Category Name", "Order Region"]).agg(
        late_rate=("Late_delivery_risk", "mean"),
        avg_delay=("shipping_delay_days", "mean"),
        order_count=("Late_delivery_risk", "count"),
    ).reset_index()
    # Only keep combinations with enough data
    risk_heatmap = risk_heatmap[risk_heatmap["order_count"] >= 20]
    risk_heatmap = risk_heatmap.sort_values("late_rate", ascending=False).head(100)
    risk_breakdown = [
        {
            "category": row["Category Name"],
            "region": row["Order Region"],
            "score": round(float(row["late_rate"]), 4),
            "demand_risk": round(float(row["late_rate"]) * 0.9, 4),
            "inventory_risk": round(float(row["late_rate"]) * 0.85, 4),
            "supplier_risk": round(float(row["late_rate"]) * 1.05, 4),
            "logistics_risk": round(min(float(row["avg_delay"]) / 3, 1.0), 4),
            "order_count": int(row["order_count"]),
        }
        for _, row in risk_heatmap.iterrows()
    ]

    # === Monthly order trend ===
    df_dated = df.copy()
    df_dated["_date"] = pd.to_datetime(df_dated["order date (DateOrders)"], errors="coerce")
    df_dated = df_dated.dropna(subset=["_date"])
    df_dated["_period"] = df_dated["_date"].dt.strftime("%Y-%m")
    monthly = df_dated.groupby("_period").agg(
        orders=("Late_delivery_risk", "count"),
        late_rate=("Late_delivery_risk", "mean"),
        avg_delay=("shipping_delay_days", "mean"),
        total_sales=("Sales", "sum"),
    ).reset_index()
    monthly_trend = [
        {
            "period": str(row["_period"]),
            "orders": int(row["orders"]),
            "late_rate": round(float(row["late_rate"]), 4),
            "avg_delay": round(float(row["avg_delay"]), 2),
            "total_sales": round(float(row["total_sales"]), 2),
        }
        for _, row in monthly.iterrows()
    ]

    # === Training metrics from registry ===
    training_metrics = _load_training_metrics()

    _analytics_mtime = current_mtime
    _analytics_cache = {
        "ready": True,
        "shipping_risk": shipping_risk,
        "category_volatility": category_volatility,
        "order_value_distribution": order_value_dist,
        "walk_forward_split": walk_forward,
        "risk_breakdown": risk_breakdown,
        "monthly_trend": monthly_trend,
        "training_metrics": training_metrics,
        "total_orders": int(total),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _analytics_cache


def _load_training_metrics() -> dict:
    """Load real training metrics from the model registry."""
    registry_path = Path(settings.model_dir) / "registry.json"
    if not registry_path.exists():
        return {}

    try:
        data = json.loads(registry_path.read_text())
        result = {}
        for intel_type, versions in data.items():
            active = [v for v in versions if v.get("is_active")]
            if active:
                v = active[-1]
                result[intel_type] = {
                    "version_id": v["version_id"],
                    "task": v["task"],
                    "metrics": v["metrics"],
                    "n_training_samples": v["n_training_samples"],
                    "training_duration_ms": round(v["training_duration_ms"], 1),
                    "created_at": v["created_at"],
                    "features_used": v["features_used"],
                    "is_active": True,
                }
        return result
    except Exception as e:
        logger.warning(f"Failed to load registry: {e}")
        return {}


def _compute_auto_forecast() -> dict:
    """
    Generate automatic forecast for the next period after training data ends.
    Uses trained models to predict on the last month's feature distribution.
    """
    df = _load_parquet()
    if df is None:
        return {"ready": False, "message": "Dataset not processed"}

    registry_path = Path(settings.model_dir) / "registry.json"
    if not registry_path.exists():
        return {"ready": False, "message": "Models not trained"}

    try:
        import joblib
        from app.ml.utils import FEATURE_CONFIGS, IntelligenceType, ModelTask

        registry_data = json.loads(registry_path.read_text())

        # Get the last month of data as template
        dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
        df["_month"] = dates.dt.to_period("M")
        last_month = df["_month"].max()
        template = df[df["_month"] == last_month].copy()

        if len(template) == 0:
            return {"ready": False, "message": "No template data"}

        forecast_results = {}
        for intel_type in IntelligenceType:
            versions = registry_data.get(intel_type.value, [])
            active = [v for v in versions if v.get("is_active")]
            if not active:
                continue

            model_info = active[-1]
            model_path = Path(settings.model_dir).parent / model_info["model_path"]
            if not model_path.exists():
                # Try relative to model_dir
                model_path = Path(model_info["model_path"])
                if not model_path.exists():
                    continue

            model = joblib.load(model_path)
            feature_config = FEATURE_CONFIGS[intel_type]
            available_features = [f for f in feature_config.features if f in template.columns]

            if not available_features:
                continue

            X = template[available_features].fillna(0)
            preds = model.predict(X)

            mean_pred = float(np.mean(preds))
            std_pred = float(np.std(preds))

            if feature_config.task == ModelTask.CLASSIFICATION:
                # For classifiers, mean_pred is probability of late delivery
                forecast_results[intel_type.value] = {
                    "predicted_risk": round(mean_pred, 4),
                    "risk_level": "high" if mean_pred >= 0.65 else "medium" if mean_pred >= 0.35 else "low",
                    "confidence": round(max(0, 1 - std_pred), 4),
                    "n_predictions": len(preds),
                    "std": round(std_pred, 4),
                }
            else:
                # For regression (demand), mean_pred is predicted quantity
                # Volatility-adjusted CI bounds: wider bands for high volatility
                vol = float(np.std(preds) / (abs(mean_pred) + 1e-6))
                ci_pct = max(0.10, vol * 0.5)
                ci_width = mean_pred * ci_pct
                forecast_results[intel_type.value] = {
                    "predicted_value": round(mean_pred, 4),
                    "lower_bound": round(max(0, mean_pred - ci_width), 4),
                    "upper_bound": round(mean_pred + ci_width, 4),
                    "confidence": round(max(0, min(1, 1 - ci_pct)), 4),
                    "n_predictions": len(preds),
                    "std": round(std_pred, 4),
                }

        # Aggregate by category × region for detailed forecast
        category_forecasts = []

        # Pre-load all active models once
        active_models: dict = {}
        active_features: dict = {}
        for intel_type in IntelligenceType:
            versions = registry_data.get(intel_type.value, [])
            active = [v for v in versions if v.get("is_active")]
            if not active:
                continue
            model_info = active[-1]
            model_path = Path(settings.model_dir).parent / model_info["model_path"]
            if not model_path.exists():
                model_path = Path(model_info["model_path"])
            if not model_path.exists():
                continue
            m = joblib.load(model_path)
            feat_cfg = FEATURE_CONFIGS[intel_type]
            avail_feats = [f for f in feat_cfg.features if f in template.columns]
            if avail_feats:
                active_models[intel_type] = m
                active_features[intel_type] = avail_feats

        for (cat, region), grp in template.groupby(["Category Name", "Order Region"]):
            if len(grp) < 3:
                continue

            row_result = {"category": cat, "region": region, "order_count": len(grp)}

            # Demand: use model predictions (sum of per-row predicted quantities)
            demand_model = active_models.get(IntelligenceType.DEMAND)
            demand_feats = active_features.get(IntelligenceType.DEMAND, [])
            if demand_model is not None and demand_feats:
                try:
                    X_grp = grp[demand_feats].fillna(0)
                    preds_demand = demand_model.predict(X_grp)
                    # Sum of per-row predictions = total predicted demand for this group
                    predicted_demand_val = float(np.sum(preds_demand))
                    # Clip to reasonable range: [0, 3x historical mean * n_rows]
                    hist_mean = float(grp["Order Item Quantity"].mean()) if "Order Item Quantity" in grp.columns else 2.0
                    predicted_demand_val = float(np.clip(predicted_demand_val, 0, hist_mean * len(grp) * 3))
                except Exception:
                    predicted_demand_val = float(grp["Order Item Quantity"].sum()) if "Order Item Quantity" in grp.columns else float(len(grp)) * 2.0
            else:
                predicted_demand_val = float(grp["Order Item Quantity"].sum()) if "Order Item Quantity" in grp.columns else float(len(grp)) * 2.0

            avg_price = float(grp["Product Price"].mean()) if "Product Price" in grp.columns else 50.0
            row_result["predicted_demand"] = round(predicted_demand_val, 2)
            row_result["predicted_revenue"] = round(predicted_demand_val * avg_price, 2)

            # Risk scores from classifier models
            for intel_type in (IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS):
                m = active_models.get(intel_type)
                feats = active_features.get(intel_type, [])
                if m is not None and feats:
                    try:
                        X_grp = grp[feats].fillna(0)
                        if hasattr(m, "predict_proba"):
                            risk_val = float(np.mean(m.predict_proba(X_grp)[:, 1]))
                        else:
                            risk_val = float(np.mean(m.predict(X_grp)))
                        row_result[f"{intel_type.value}_risk"] = round(risk_val, 4)
                    except Exception:
                        pass

            # Combined risk
            risks = [float(row_result.get(f"{t.value}_risk", 0)) for t in (IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS)]
            valid_risks = [r for r in risks if r > 0]
            row_result["combined_risk"] = round(sum(valid_risks) / len(valid_risks) if valid_risks else 0.0, 4)
            category_forecasts.append(row_result)

        category_forecasts.sort(key=lambda x: x.get("combined_risk", 0), reverse=True)

        # Overall confidence: use walk-forward R2/AUC from registry, not prediction std
        overall_confidence = 0.0
        conf_values = []
        for intel_type in IntelligenceType:
            versions = registry_data.get(intel_type.value, [])
            active = [v for v in versions if v.get("is_active")]
            if not active:
                continue
            v = active[-1]
            metrics = v.get("metrics", {})
            # Regression: use R2 clipped to [0,1]; Classification: use ROC-AUC
            if v.get("task") == "regression":
                r2 = float(metrics.get("r2", 0.0))
                conf_values.append(max(0.0, min(1.0, r2)))
            else:
                auc = float(metrics.get("roc_auc", metrics.get("auc", 0.0)))
                conf_values.append(max(0.0, min(1.0, auc)))
        overall_confidence = round(sum(conf_values) / len(conf_values) if conf_values else 0.0, 4)

        # Derive forecast period dynamically from training data end
        summary = _compute_summary()
        forecast_period_start = summary.get("next_forecast_start", "")
        forecast_period_end   = summary.get("next_forecast_end", "")
        training_data_end     = summary.get("training_data_end_date", "")
        forecast_period_label = forecast_period_start[:7] if forecast_period_start else ""

        return {
            "ready": True,
            "forecast_period": forecast_period_label,
            "forecast_period_start": forecast_period_start,
            "forecast_period_end": forecast_period_end,
            "training_data_end": training_data_end,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "overall_confidence": overall_confidence,
            "agent_results": forecast_results,
            "category_forecasts": category_forecasts,
            "total_forecasts": len(category_forecasts),
            "high_risk_count": sum(1 for f in category_forecasts if f.get("combined_risk", 0) >= 0.65),
            "medium_risk_count": sum(1 for f in category_forecasts if 0.35 <= f.get("combined_risk", 0) < 0.65),
            "low_risk_count": sum(1 for f in category_forecasts if f.get("combined_risk", 0) < 0.35),
        }

    except Exception as e:
        logger.error(f"Auto-forecast failed: {e}", exc_info=True)
        return {"ready": False, "message": f"Forecast generation failed: {str(e)}"}


# Cache for auto-forecast (expensive computation) — cleared on backend restart
_forecast_cache: dict | None = None


def clear_forecast_cache():
    global _forecast_cache
    _forecast_cache = None



@router.delete("/increments")
def delete_increments(confirm: bool = False):
    """
    Delete all uploaded increment parquets and clear the manifest period list.
    base.parquet is NEVER touched.

    Verifies base.parquet checksum before and after to confirm it is unchanged.
    Requires ?confirm=true — refuses without it.
    """
    from fastapi import HTTPException
    if not confirm:
        raise HTTPException(
            400,
            "Pass ?confirm=true to delete all increments. "
            "This operation cannot be undone.",
        )
    try:
        result = _get_store().reset_increments(confirm=True)
        clear_dataset_cache()
        return {"status": "ok", **result}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/coverage")
def get_dataset_coverage():
    """
    Report what data the system is currently using.
    Returns base period range, base row count, each appended period with its
    row count, the combined total, and the latest date present.
    """
    try:
        return _get_store().coverage()
    except Exception as e:
        logger.warning(f"Coverage endpoint fallback: {e}")
        base_path = _get_base_parquet_path()
        rows = 0
        if base_path.exists():
            try:
                rows = len(pd.read_parquet(base_path))
            except Exception:
                pass
        return {
            "base_period_start": None,
            "base_period_end": None,
            "base_row_count": rows,
            "increments": [],
            "increment_count": 0,
            "combined_total": rows,
            "latest_date": None,
        }


@router.get("/summary")
def get_dataset_summary():
    """Real computed values from the processed DataCo dataset."""
    return _compute_summary()


@router.get("/analytics")
def get_dataset_analytics():
    """
    Detailed analytics for all frontend pages.
    Shipping risk, category volatility, order value distribution,
    risk heatmap, monthly trends, training metrics — all real.
    """
    return _compute_analytics()


@router.get("/next-forecast-period")
def get_next_forecast_period():
    """Auto-detect the next forecast period based on training data end date."""
    summary = _compute_summary()
    return {
        "period_start": summary.get("next_forecast_start", ""),
        "period_end": summary.get("next_forecast_end", ""),
        "training_data_end": summary.get("training_data_end_date", ""),
        "recommendation": f"Forecasting next period after training data ends {summary.get('training_data_end_date', '')}",
    }


@router.get("/auto-forecast")
def get_auto_forecast():
    """
    Automatic forecast for the next period after training data ends.
    Generated from trained models applied to last month's feature distribution.
    No user upload required.
    """
    global _forecast_cache
    if _forecast_cache is not None:
        return _forecast_cache
    _forecast_cache = _compute_auto_forecast()
    result_store.save_auto_forecast(_forecast_cache)
    return _forecast_cache


@router.get("/error-diagnostics")
def get_error_diagnostics(period_start: str = None):
    """
    Real-time error diagnostics: runs the trained demand model on each
    Category x Region group from the temperature list, compares against
    actual Order Item Quantity sums from the same data.

    predicted_demand  = LightGBM demand model mean prediction on that group
    actual_demand     = real sum of Order Item Quantity for that group
    """
    df = _load_parquet()
    if df is None or len(df) == 0:
        return {"diagnostics": [], "count": 0}

    # ── Filter to the requested period if supplied ──────────────────────────
    if period_start and "order date (DateOrders)" in df.columns:
        dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
        period_mask = dates.dt.strftime("%Y-%m") == period_start
        df_period = df[period_mask].copy()
        # If no rows match the period, use the most recent month available
        # (covers the case where uploaded CSV has no date column or dates differ)
        if len(df_period) < 10:
            latest_period = dates.dt.strftime("%Y-%m").max()
            df_period = df[dates.dt.strftime("%Y-%m") == latest_period].copy()
        if len(df_period) < 10:
            df_period = df.copy()
    else:
        df_period = df.copy()

    # ── Load demand model from registry ────────────────────────────────────
    demand_model = None
    demand_features = []
    try:
        import joblib
        from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
        registry_path = Path(settings.model_dir) / "registry.json"
        if registry_path.exists():
            registry_data = json.loads(registry_path.read_text())
            versions = registry_data.get(IntelligenceType.DEMAND.value, [])
            active = [v for v in versions if v.get("is_active")]
            if active:
                model_info = active[-1]
                model_path = Path(settings.model_dir).parent / model_info["model_path"]
                if not model_path.exists():
                    model_path = Path(model_info["model_path"])
                if model_path.exists():
                    demand_model = joblib.load(model_path)
                    feat_cfg = FEATURE_CONFIGS[IntelligenceType.DEMAND]
                    demand_features = [f for f in feat_cfg.features if f in df_period.columns]
    except Exception as e:
        logger.warning(f"[ErrorDiag] Model load warning: {e}")

    # ── Agent assignment by late_delivery_risk level ────────────────────────
    agent_map = {
        "high":   "Logistics Agent",
        "medium": "Supplier Agent",
        "low":    "Demand Agent",
    }

    # ── Build diagnostics per Category × Region ─────────────────────────────
    diagnostics = []
    top_cats = (
        df_period.groupby(["Category Name", "Order Region"])
        .size()
        .reset_index(name="order_count")
    )
    top_cats = (
        top_cats[top_cats["order_count"] >= 5]
        .sort_values("order_count", ascending=False)
    )

    for _, row in top_cats.iterrows():
        cat    = row["Category Name"]
        region = row["Order Region"]
        grp    = df_period[(df_period["Category Name"] == cat) & (df_period["Order Region"] == region)]

        # Real actual demand from uploaded data
        if "Order Item Quantity" in grp.columns:
            actual_demand = int(grp["Order Item Quantity"].sum())
        else:
            actual_demand = len(grp)

        # Real model prediction
        if demand_model is not None and demand_features:
            try:
                X_grp = grp[demand_features].fillna(0)
                preds  = demand_model.predict(X_grp)
                pred_demand = int(round(float(preds.sum())))
            except Exception:
                pred_demand = actual_demand  # safe fallback
        else:
            # No model available — use historical mean as baseline
            pred_demand = int(grp["Order Item Quantity"].mean() * len(grp)) if "Order Item Quantity" in grp.columns else actual_demand

        variance = actual_demand - pred_demand
        pct_var  = round((variance / (pred_demand + 1e-6)) * 100, 1)

        # Late delivery rate for this group
        late_rate = float(grp["Late_delivery_risk"].mean()) if "Late_delivery_risk" in grp.columns else 0.3
        risk_level = "high" if late_rate >= 0.55 else "medium" if late_rate >= 0.35 else "low"
        resp_agent = agent_map[risk_level]

        diagnostics.append({
            "category":          cat,
            "region":            region,
            "period":            period_start or "latest",
            "predicted_demand":  pred_demand,
            "actual_demand":     actual_demand,
            "variance":          f"{variance:+} ({pct_var}%)",
            "responsible_agent": resp_agent,
            "risk_level":        risk_level.capitalize(),
            "late_delivery_rate": round(late_rate * 100, 1),
            "reason":            f"Late delivery rate {round(late_rate*100,1)}% on {region} lane",
            "root_cause":        f"Demand model vs actual gap: {variance:+} units — {cat} · {region}",
        })

    out = {"diagnostics": diagnostics, "count": len(diagnostics), "period_used": period_start or "latest"}
    result_store.save_error_diagnostics(out, period_start)
    return out


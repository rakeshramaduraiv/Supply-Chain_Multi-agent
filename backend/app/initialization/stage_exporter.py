"""
AMASCI Stage Exporter
======================
Writes per-stage tabular CSV artifacts.
All writes are best-effort — failures log a warning and never propagate.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_PII = [
    "Customer Email", "Customer Password", "Customer Street",
    "Customer Fname", "Customer Lname", "Customer Zipcode",
    "Order Zipcode", "Product Description",
]

# 13 raw DataCo columns that are the actual inputs to feature engineering
FE_INPUT_COLS = [
    "order date (DateOrders)",
    "Order Item Quantity",
    "Product Price",
    "Order Item Discount",
    "Sales",
    "Days for shipment (scheduled)",
    "Days for shipping (real)",
    "Department Name",
    "Shipping Mode",
    "Order Region",
    "Category Name",
    "Late_delivery_risk",
    "Order Country",
]


def _redact(df: pd.DataFrame) -> pd.DataFrame:
    present = [c for c in _PII if c in df.columns]
    if present:
        df = df.drop(columns=present)
    return df


def _profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        non_null = int(df[col].notna().sum())
        null_pct = round(df[col].isna().sum() / max(len(df), 1) * 100, 2)
        n_unique = int(df[col].nunique(dropna=False))
        sample_val = ""
        try:
            nonnull = df[col].dropna()
            sample_val = str(nonnull.iloc[0]) if len(nonnull) else ""
        except Exception:
            pass
        row: dict[str, Any] = {
            "column": col, "dtype": str(df[col].dtype),
            "non_null": non_null, "null_pct": null_pct,
            "n_unique": n_unique,
            "mean": "", "std": "", "min": "", "max": "",
            "sample_value": sample_val,
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            s = df[col].dropna()
            if len(s):
                row.update({
                    "mean": round(float(s.mean()), 6),
                    "std":  round(float(s.std()),  6),
                    "min":  round(float(s.min()),  6),
                    "max":  round(float(s.max()),  6),
                })
        rows.append(row)
    return pd.DataFrame(rows)


def _safe(fn):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:
            logger.warning(f"StageExporter.{fn.__name__} failed: {exc}", exc_info=True)
            return None
    return wrapper


class StageExporter:
    """
    Writes per-stage tabular artifacts to out_dir/.
    No-op when disabled=True.
    """

    def __init__(self, out_dir: str | None = None, sample_rows: int = 2000,
                 disabled: bool = False):
        self._dir = Path(out_dir or "data/stages")
        self._half = sample_rows // 2
        self._disabled = disabled
        self._manifest: list[dict[str, Any]] = []
        self._prev_cols: set[str] = set()

        if not disabled:
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logger.warning(f"StageExporter: cannot create {self._dir}: {exc}")
                self._disabled = True

    # ── public ────────────────────────────────────────────────────────────────

    def export(self, step: int, name: str, df: pd.DataFrame,
               notes: str = "") -> dict[str, Any]:
        if self._disabled:
            return {}
        try:
            return self._export(step, name, df, notes)
        except Exception as exc:
            logger.warning(f"StageExporter.export step={step} failed: {exc}", exc_info=True)
            return {}

    def write_preprocessing_csv(self, df: pd.DataFrame) -> None:
        """Write full preprocessed DataFrame (post-pipeline, pre-FE) as CSV."""
        if self._disabled:
            return
        try:
            self._write_preprocessing_csv(df)
        except Exception as exc:
            logger.warning(f"StageExporter.write_preprocessing_csv failed: {exc}", exc_info=True)

    def write_fe_inputs_csv(self, df: pd.DataFrame) -> None:
        """Write only the 13 columns that are actual inputs to feature engineering."""
        if self._disabled:
            return
        try:
            self._write_fe_inputs_csv(df)
        except Exception as exc:
            logger.warning(f"StageExporter.write_fe_inputs_csv failed: {exc}", exc_info=True)

    def write_feature_groups(self, df: pd.DataFrame) -> None:
        """Write one CSV per FE group — 8 files under data/stages/feature_groups/."""
        if self._disabled:
            return
        try:
            self._write_feature_groups(df)
        except Exception as exc:
            logger.warning(f"StageExporter.write_feature_groups failed: {exc}", exc_info=True)

    def write_graph_delta(self, df_enriched: pd.DataFrame, tier1: pd.DataFrame) -> None:
        if self._disabled:
            return
        try:
            self._write_graph_delta(df_enriched, tier1)
        except Exception as exc:
            logger.warning(f"StageExporter.write_graph_delta failed: {exc}", exc_info=True)

    def write_model_results(self, training_results: dict[str, Any]) -> None:
        if self._disabled:
            return
        try:
            self._write_model_results(training_results)
        except Exception as exc:
            logger.warning(f"StageExporter.write_model_results failed: {exc}", exc_info=True)

    def write_registry_summary(self) -> None:
        if self._disabled:
            return
        try:
            self._write_registry_summary()
        except Exception as exc:
            logger.warning(f"StageExporter.write_registry_summary failed: {exc}", exc_info=True)

    def finalize(self) -> None:
        if self._disabled or not self._manifest:
            return
        try:
            self._finalize()
        except Exception as exc:
            logger.warning(f"StageExporter.finalize failed: {exc}", exc_info=True)

    # ── internals ─────────────────────────────────────────────────────────────

    def _export(self, step: int, name: str, df: pd.DataFrame, notes: str) -> dict[str, Any]:
        df = _redact(df.copy())
        prefix = f"{step}_{name}"

        h = min(self._half, len(df))
        t = min(self._half, max(0, len(df) - h))
        sample = pd.concat([df.iloc[:h], df.iloc[len(df) - t:]], ignore_index=True)
        sample.to_csv(self._dir / f"{prefix}_sample.csv", index=False)
        df.to_parquet(self._dir / f"{prefix}_full.parquet", index=False)
        _profile(df).to_csv(self._dir / f"{prefix}_profile.csv", index=False)

        cur = set(df.columns)
        added   = sorted(cur - self._prev_cols)
        removed = sorted(self._prev_cols - cur)
        mem_mb  = round(df.memory_usage(deep=True).sum() / 1_048_576, 2)

        rec: dict[str, Any] = {
            "step": step, "name": name,
            "rows": len(df), "cols": len(df.columns),
            "columns_added": added, "columns_removed": removed,
            "memory_mb": mem_mb,
            "duration_note": notes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._manifest.append(rec)
        self._prev_cols = cur
        logger.info(f"StageExporter step={step} '{name}': "
                    f"{len(df):,}r × {len(df.columns)}c "
                    f"+{len(added)} -{len(removed)} cols")
        return rec

    @_safe
    def _write_preprocessing_csv(self, df: pd.DataFrame) -> None:
        """
        Full preprocessed data — 48 cols (no PII, no IDs).
        Raw DataCo columns + 13 transformation columns.
        """
        df = _redact(df.copy())
        df.to_csv(self._dir / "2_preprocessed_full.csv", index=False)
        logger.info(f"StageExporter: wrote 2_preprocessed_full.csv "
                    f"({len(df):,}r × {len(df.columns)}c)")

    @_safe
    def _write_fe_inputs_csv(self, df: pd.DataFrame) -> None:
        """
        Only the 13 raw columns that are direct inputs to feature engineering.
        This is the exact data that engineer_features() reads from.
        """
        present = [c for c in FE_INPUT_COLS if c in df.columns]
        df[present].to_csv(self._dir / "2_fe_inputs.csv", index=False)
        logger.info(f"StageExporter: wrote 2_fe_inputs.csv "
                    f"({len(df):,}r × {len(present)} FE input cols)")

    @_safe
    def _write_feature_groups(self, df: pd.DataFrame) -> None:
        from app.feature_engineering import ENGINEERED_FEATURES
        fe_set = set(ENGINEERED_FEATURES)

        _EXTRA: dict[str, list[str]] = {
            "temporal": ["period_monthly", "order_day_of_week", "order_is_weekend"],
            "demand_rolling": [
                "demand_volatility", "demand_trend_slope", "demand_spike_flag",
                "demand_momentum", "order_value_log", "revenue_per_unit",
                "category_demand_rank",
                "rolling_7d_demand", "rolling_14d_demand", "rolling_30d_demand",
                "demand_lag_1m", "demand_lag_3m", "demand_trend",
            ],
            "inventory": ["stock_coverage_ratio"],
            "supplier": [
                "supplier_reliability_score", "supplier_delay_rate",
                "supplier_risk_index", "supplier_volume",
            ],
            "logistics": ["region_congestion_index", "shipping_mode_encoded"],
            "post_shipment": ["composite_risk_score"],
            "aliases": [
                "shipping_delay", "shipping_efficiency_score", "is_weekend_order",
                "order_value_tier", "delay_category", "is_holiday_week",
            ],
        }

        GROUPS: list[tuple[str, list[str]]] = [
            ("3a_temporal", [
                "order_year", "order_month", "order_dayofweek", "order_quarter",
                "is_weekend", "is_holiday_period",
                *_EXTRA["temporal"],
            ]),
            ("3b_demand_rolling", [
                "qty_roll_7", "qty_roll_30", "qty_lag_1", "qty_lag_7", "qty_lag_30",
                "price_ratio", "discount_rate",
                *_EXTRA["demand_rolling"],
            ]),
            ("3c_inventory", [
                "inventory_stress_index", "days_until_reorder", "reorder_point",
                "demand_variability",
                *_EXTRA["inventory"],
            ]),
            ("3d_supplier", [
                "supplier_hist_late_rate", "supplier_order_volume",
                "supplier_category_diversity",
                *_EXTRA["supplier"],
            ]),
            ("3e_logistics", [
                "route_hist_late_rate", "region_hist_late_rate",
                "shipmode_hist_late_rate", "route_frequency", "days_scheduled",
                *_EXTRA["logistics"],
            ]),
            ("3f_post_shipment", [
                "delivery_gap", "is_delayed", "delivery_duration_days",
                "shipping_delay_ratio",
                *_EXTRA["post_shipment"],
            ]),
            ("3g_graph_context", [
                "graph_supplier_reliability", "graph_inventory_stress",
                "graph_avg_shipping_delay", "graph_tpke_edge_density",
            ]),
            ("3h_aliases", _EXTRA["aliases"]),
        ]

        fg_dir = self._dir / "feature_groups"
        fg_dir.mkdir(parents=True, exist_ok=True)

        df = _redact(df.copy())

        for prefix, feat_cols in GROUPS:
            present = [c for c in feat_cols if c in df.columns]
            if not present:
                logger.warning(f"StageExporter: {prefix} — no columns found, skipping")
                continue
            df[present].to_csv(fg_dir / f"{prefix}.csv", index=False)
            logger.info(f"StageExporter: wrote {prefix}.csv ({len(present)} cols)")

        # Combined — all engineered feature columns only
        all_fe = [c for c in df.columns
                  if c in fe_set or any(c in v for v in _EXTRA.values())]
        if all_fe:
            df[all_fe].to_csv(fg_dir / "3_all_features_combined.csv", index=False)
            logger.info(f"StageExporter: wrote 3_all_features_combined.csv ({len(all_fe)} cols)")

    @_safe
    def _write_graph_delta(self, df_enriched: pd.DataFrame, tier1: pd.DataFrame) -> None:
        from app.ml.utils import GRAPH_CONTEXT_FEATURES
        summary_rows, detail_rows = [], []
        for col in GRAPH_CONTEXT_FEATURES:
            if col not in df_enriched.columns or col not in tier1.columns:
                continue
            t1 = tier1[col].astype(float).reset_index(drop=True)
            t2 = df_enriched[col].astype(float).reset_index(drop=True)
            diff = (t2 - t1).abs()
            changed = int((diff > 1e-9).sum())
            corr = float(t1.corr(t2)) if t1.std() > 0 and t2.std() > 0 else 1.0
            summary_rows.append({
                "column": col,
                "tier1_mean": round(float(t1.mean()), 6),
                "tier2_mean": round(float(t2.mean()), 6),
                "mean_absolute_change": round(float(diff.mean()), 6),
                "max_absolute_change":  round(float(diff.max()),  6),
                "pct_rows_changed":     round(changed / max(len(t1), 1) * 100, 2),
                "pearson_tier1_vs_tier2": round(corr, 6),
            })
            idx = list(range(min(250, len(t1)))) + \
                  list(range(max(0, len(t1) - 250), len(t1)))
            for i in idx:
                detail_rows.append({
                    "row_index": i, "column": col,
                    "tier1_value": round(float(t1.iloc[i]), 6),
                    "tier2_value": round(float(t2.iloc[i]), 6),
                    "delta":       round(float(t2.iloc[i] - t1.iloc[i]), 6),
                })
        if summary_rows:
            pd.DataFrame(summary_rows).to_csv(self._dir / "4_graph_feature_delta.csv", index=False)
        if detail_rows:
            pd.DataFrame(detail_rows).to_csv(self._dir / "4_graph_delta_rows.csv", index=False)
        logger.info("StageExporter: wrote graph delta files")

    @_safe
    def _write_model_results(self, training_results: dict[str, Any]) -> None:
        from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
        metric_rows, fold_rows, fi_rows = [], [], []
        for agent, result in training_results.items():
            try:
                intel = IntelligenceType(agent)
                fc = FEATURE_CONFIGS.get(intel)
                n_features = len(fc.features) if fc else 0
            except Exception:
                n_features = 0
            m = result.metrics if hasattr(result, "metrics") else result.get("metrics", {})
            metric_rows.append({
                "agent": agent,
                "model_type": getattr(result, "task", ""),
                "target": getattr(result, "intelligence_type", agent),
                "n_features": n_features,
                "train_rows": getattr(result, "n_training_samples", ""),
                "test_rows":  getattr(result, "n_test_samples", ""),
                **{k: round(v, 6) if isinstance(v, float) else v for k, v in m.items()},
            })
            wf = getattr(result, "walk_forward_result", None) or {}
            for fold in wf.get("folds", []):
                fold_rows.append({
                    "agent": agent,
                    "fold": fold.get("fold_index", ""),
                    "train_rows": fold.get("train_size", ""),
                    "test_rows":  fold.get("test_size", ""),
                    "test_period": fold.get("test_period", ""),
                    "metric_value": fold.get("metric_value", ""),
                    **{f"metric_{k}": round(v, 6) if isinstance(v, float) else v
                       for k, v in fold.get("metrics", {}).items()},
                })
            fi = getattr(result, "feature_importance", {})
            for feat, imp in (fi.get("importance_scores") or {}).items():
                fi_rows.append({"agent": agent, "feature": feat,
                                "importance": round(float(imp), 6)})
        if metric_rows:
            pd.DataFrame(metric_rows).to_csv(self._dir / "5_model_metrics.csv", index=False)
        if fold_rows:
            pd.DataFrame(fold_rows).to_csv(self._dir / "5_walk_forward_folds.csv", index=False)
        if fi_rows:
            fi_df = pd.DataFrame(fi_rows)
            fi_df["rank"] = fi_df.groupby("agent")["importance"] \
                              .rank(ascending=False, method="min").astype(int)
            fi_df.sort_values(["agent", "rank"]).to_csv(
                self._dir / "5_feature_importance.csv", index=False)
        logger.info("StageExporter: wrote model result files")

    @_safe
    def _write_registry_summary(self) -> None:
        from app.ml.registry import ModelRegistry
        registry = ModelRegistry()
        all_models = registry.list_all_models()
        rows = []
        for agent, versions in all_models.items():
            for v in versions:
                rows.append({
                    "agent":      agent,
                    "version":    v.get("version_id", ""),
                    "active":     v.get("is_active", ""),
                    "created_at": v.get("created_at", ""),
                    "metrics":    json.dumps(v.get("metrics", {})),
                })
        if rows:
            pd.DataFrame(rows).to_csv(self._dir / "6_registry_summary.csv", index=False)
        logger.info("StageExporter: wrote registry summary")

    def _finalize(self) -> None:
        flat = []
        for r in self._manifest:
            flat.append({**r,
                "columns_added":   "|".join(r["columns_added"]),
                "columns_removed": "|".join(r["columns_removed"]),
            })
        pd.DataFrame(flat).to_csv(self._dir / "00_pipeline_summary.csv", index=False)

        with open(self._dir / "00_pipeline_summary.json", "w") as fh:
            json.dump(self._manifest, fh, indent=2, default=str)

        stage_cols: dict[int, set[str]] = {}
        all_cols: set[str] = set()
        for r in self._manifest:
            prof = self._dir / f"{r['step']}_{r['name']}_profile.csv"
            cols: set[str] = set()
            if prof.exists():
                cols = set(pd.read_csv(prof)["column"].tolist())
            stage_cols[r["step"]] = cols
            all_cols |= cols

        lineage = []
        steps = sorted(stage_cols)
        for col in sorted(all_cols):
            row: dict[str, Any] = {"column": col}
            for s in steps:
                nm = next((r["name"] for r in self._manifest if r["step"] == s), str(s))
                row[f"s{s:02d}_{nm}"] = col in stage_cols.get(s, set())
            lineage.append(row)
        pd.DataFrame(lineage).to_csv(self._dir / "00_column_lineage.csv", index=False)

        logger.info(f"StageExporter: finalized — {len(self._manifest)} stages, "
                    f"{len(all_cols)} unique columns")

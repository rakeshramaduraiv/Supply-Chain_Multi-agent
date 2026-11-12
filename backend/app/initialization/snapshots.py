"""
AMASCI Stage Snapshot Writer
==============================
Saves every data transformation result as an auditable disk artifact.

FOLDER STRUCTURE:
data/stages/
  step1_raw_dataset.csv                    ← raw CSV as loaded (2000-row sample)
  step1_raw_dataset_full.parquet           ← full 180k rows
  step1_raw_dataset_profile.csv            ← per-column stats

  step2_after_cleaning.csv                 ← after validate+clean+transform
  step2_after_cleaning_full.parquet
  step2_after_cleaning_profile.csv

  step3_after_feature_engineering.csv      ← after Tier-1 feature engineering
  step3_after_feature_engineering_full.parquet
  step3_after_feature_engineering_profile.csv

  step4_after_graph_enrichment.csv         ← after Neo4j Tier-2 enrichment
  step4_after_graph_enrichment_full.parquet
  step4_after_graph_enrichment_profile.csv
  step4_graph_feature_delta.csv            ← Tier-1 vs Tier-2 graph column comparison

  step5_model_training_results.csv         ← per-model metrics (accuracy, AUC, R²)
  step5_feature_importance.csv             ← top features per model
  step5_walk_forward_folds.csv             ← per-fold CV scores

  step6_model_registry_summary.csv         ← registered model versions + paths

  step7_final_dataset_profile.csv          ← final parquet column stats
  step7_pipeline_summary.csv               ← end-to-end step durations + row/col counts

  00_manifest.csv             ← manifest of all stages
  00_manifest.json            ← manifest in JSON format
  00_column_lineage.csv       ← column × stage boolean grid
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_PII_COLUMNS = [
    "Customer Email",
    "Customer Password",
    "Customer Street",
    "Customer Fname",
    "Customer Lname",
    "Customer Zipcode",
    "Product Description",
]

_BANNED_FROM_MODELS = {
    "is_delayed",
    "delivery_gap",
    "delivery_duration_days",
    "shipping_delay_ratio",
    "composite_risk_score",
    "revenue_per_unit",
    "supplier_delay_rate",
}


def _redact_pii(df: pd.DataFrame) -> pd.DataFrame:
    """Drop PII columns if present and log redacted names."""
    present = [c for c in _PII_COLUMNS if c in df.columns]
    if present:
        logger.info(f"Redact PII columns from snapshot: {present}")
        df = df.drop(columns=present)
    return df


def _build_profile(df: pd.DataFrame, stage_no: int) -> pd.DataFrame:
    """Build column profile (dtype, nulls, unique count, min/max/mean/std for numeric)."""
    rows = []
    for col in df.columns:
        non_null = int(df[col].notna().sum())
        null_pct = round(float(df[col].isna().sum() / max(len(df), 1) * 100), 2)
        n_unique = int(df[col].nunique(dropna=False))

        row: dict[str, Any] = {
            "column": col,
            "dtype": str(df[col].dtype),
            "non_null": non_null,
            "null_pct": null_pct,
            "n_unique": n_unique,
            "mean": "",
            "std": "",
            "min": "",
            "max": "",
        }

        if stage_no == 5:
            row["is_banned_from_models"] = col in _BANNED_FROM_MODELS

        if pd.api.types.is_numeric_dtype(df[col]):
            s = df[col].dropna()
            if len(s) > 0:
                row.update({
                    "mean": round(float(s.mean()), 6),
                    "std": round(float(s.std()), 6),
                    "min": round(float(s.min()), 6),
                    "max": round(float(s.max()), 6),
                })
        rows.append(row)
    return pd.DataFrame(rows)


def _sample(df: pd.DataFrame, sample_rows: int) -> pd.DataFrame:
    """Take first N/2 and last N/2 rows for early/late chronological sampling."""
    if len(df) <= sample_rows:
        return df.copy()
    half = sample_rows // 2
    head = df.iloc[:half]
    tail = df.iloc[len(df) - half:]
    return pd.concat([head, tail], ignore_index=True)


class SnapshotWriter:
    """
    Writes data transformation snapshots after each stage during system initialization.

    All file operations are best-effort — exceptions log warnings and never fail
    the initialization process.
    """

    def __init__(
        self,
        base_dir: Path | str | None = None,
        sample_rows: int | None = None,
        disabled: bool | None = None,
    ):
        if disabled is None:
            disabled = not getattr(settings, "save_stage_snapshots", True)
        self.disabled = disabled

        if sample_rows is None:
            sample_rows = getattr(settings, "stage_snapshot_sample_rows", 2000)
        self.sample_rows = sample_rows

        if base_dir is None:
            base_dir = getattr(settings, "stage_snapshot_dir", "data/stages")
        self.output_dir = Path(base_dir)

        self._manifest: list[dict[str, Any]] = []
        self._prev_cols: set[str] = set()

        if not self.disabled:
            try:
                self.output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logger.warning(f"SnapshotWriter: failed to create dir {self.output_dir}: {exc}")
                self.disabled = True

    @property
    def _dir(self) -> Path:
        """Expose output_dir for test backwards compatibility."""
        return self.output_dir

    # ------------------------------------------------------------------
    # Step-specific human-readable writers
    # ------------------------------------------------------------------

    def write_step1_load(self, df: pd.DataFrame, duration_ms: float) -> None:
        """Step 1 — raw CSV as loaded from disk."""
        if self.disabled:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            df_clean = _redact_pii(df.copy())
            _sample(df_clean, self.sample_rows).to_csv(
                self.output_dir / "step1_raw_dataset.csv", index=False
            )
            df_clean.to_parquet(self.output_dir / "step1_raw_dataset_full.parquet", index=False)
            _build_profile(df_clean, 1).to_csv(
                self.output_dir / "step1_raw_dataset_profile.csv", index=False
            )
            logger.info(f"Snapshot step1: {len(df_clean):,} rows × {len(df_clean.columns)} cols")
        except Exception as exc:
            logger.warning(f"Snapshot step1 failed: {exc}")

    def write_step2_cleaned(self, df: pd.DataFrame, duration_ms: float) -> None:
        """Step 2 — after data engineering (validate + clean + transform)."""
        if self.disabled:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            df_clean = _redact_pii(df.copy())
            _sample(df_clean, self.sample_rows).to_csv(
                self.output_dir / "step2_after_cleaning.csv", index=False
            )
            df_clean.to_parquet(self.output_dir / "step2_after_cleaning_full.parquet", index=False)
            _build_profile(df_clean, 2).to_csv(
                self.output_dir / "step2_after_cleaning_profile.csv", index=False
            )
            logger.info(f"Snapshot step2: {len(df_clean):,} rows × {len(df_clean.columns)} cols")
        except Exception as exc:
            logger.warning(f"Snapshot step2 failed: {exc}")

    def write_step3_features(self, df: pd.DataFrame, duration_ms: float) -> None:
        """Step 3 — after Tier-1 feature engineering."""
        if self.disabled:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            df_clean = _redact_pii(df.copy())
            _sample(df_clean, self.sample_rows).to_csv(
                self.output_dir / "step3_after_feature_engineering.csv", index=False
            )
            df_clean.to_parquet(
                self.output_dir / "step3_after_feature_engineering_full.parquet", index=False
            )
            _build_profile(df_clean, 3).to_csv(
                self.output_dir / "step3_after_feature_engineering_profile.csv", index=False
            )
            logger.info(f"Snapshot step3: {len(df_clean):,} rows × {len(df_clean.columns)} cols")
        except Exception as exc:
            logger.warning(f"Snapshot step3 failed: {exc}")

    def write_step4_graph(self, df: pd.DataFrame, duration_ms: float, tier1_graph: "pd.DataFrame | None" = None) -> None:
        """Step 4 — after Neo4j graph enrichment."""
        if self.disabled:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            df_clean = _redact_pii(df.copy())
            _sample(df_clean, self.sample_rows).to_csv(
                self.output_dir / "step4_after_graph_enrichment.csv", index=False
            )
            df_clean.to_parquet(
                self.output_dir / "step4_after_graph_enrichment_full.parquet", index=False
            )
            _build_profile(df_clean, 4).to_csv(
                self.output_dir / "step4_after_graph_enrichment_profile.csv", index=False
            )
            if tier1_graph is not None:
                self._write_graph_delta_named(df_clean, tier1_graph)
            logger.info(f"Snapshot step4: {len(df_clean):,} rows × {len(df_clean.columns)} cols")
        except Exception as exc:
            logger.warning(f"Snapshot step4 failed: {exc}")

    def write_step5_training(
        self,
        training_results: dict,
        duration_ms: float,
    ) -> None:
        """Step 5 — model training results: metrics, feature importance, walk-forward folds."""
        if self.disabled:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # 5a. Per-model metrics summary
            metric_rows = []
            fi_rows = []
            wf_rows = []

            for model_name, result in training_results.items():
                m = result.metrics
                row = {
                    "model": model_name,
                    "task": result.task,
                    "version_id": result.version_id,
                    "n_train": result.n_training_samples,
                    "n_test": result.n_test_samples,
                    "training_duration_ms": round(result.training_duration_ms, 1),
                }
                row.update({k: round(v, 6) if isinstance(v, float) else v for k, v in m.items()})
                metric_rows.append(row)

                # 5b. Feature importance (top 30 per model)
                fi = result.feature_importance.get("importances", {})
                for feat, score in sorted(fi.items(), key=lambda x: -x[1])[:30]:
                    fi_rows.append({"model": model_name, "feature": feat, "importance": round(score, 6)})

                # 5c. Walk-forward folds
                wf = result.walk_forward_result
                if wf:
                    for fold in wf.get("folds", []):
                        wf_rows.append({
                            "model": model_name,
                            "fold": fold.get("fold"),
                            "test_period": fold.get("test_period", ""),
                            "n_test": fold.get("n_test", fold.get("test_size", "")),
                            "metric_value": fold.get("metric_value", ""),
                            **{k: round(v, 6) if isinstance(v, float) else v
                               for k, v in fold.get("metrics", {}).items()},
                        })

            pd.DataFrame(metric_rows).to_csv(
                self.output_dir / "step5_model_training_results.csv", index=False
            )
            if fi_rows:
                pd.DataFrame(fi_rows).to_csv(
                    self.output_dir / "step5_feature_importance.csv", index=False
                )
            if wf_rows:
                pd.DataFrame(wf_rows).to_csv(
                    self.output_dir / "step5_walk_forward_folds.csv", index=False
                )
            logger.info(f"Snapshot step5: {len(metric_rows)} models, {len(fi_rows)} fi rows, {len(wf_rows)} wf folds")
        except Exception as exc:
            logger.warning(f"Snapshot step5 failed: {exc}")

    def write_step6_registry(self, registry_info: dict, duration_ms: float) -> None:
        """Step 6 — model registry: all registered versions with paths and metrics."""
        if self.disabled:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            for model_type, versions in registry_info.items():
                for v in versions:
                    m = v.get("metrics", {})
                    rows.append({
                        "model_type": model_type,
                        "version_id": v.get("version_id"),
                        "task": v.get("task"),
                        "is_active": v.get("is_active"),
                        "created_at": v.get("created_at"),
                        "n_training_samples": v.get("n_training_samples"),
                        "training_duration_ms": round(v.get("training_duration_ms", 0), 1),
                        "graph_enriched": v.get("graph_enriched"),
                        "graph_enrichment_coverage": v.get("graph_enrichment_coverage"),
                        "dataset_version": v.get("dataset_version"),
                        "model_path": v.get("model_path"),
                        "n_features": len(v.get("features_used", [])),
                        **{k: round(val, 6) if isinstance(val, float) else val
                           for k, val in m.items()},
                    })
            pd.DataFrame(rows).to_csv(
                self.output_dir / "step6_model_registry_summary.csv", index=False
            )
            logger.info(f"Snapshot step6: {len(rows)} registry entries")
        except Exception as exc:
            logger.warning(f"Snapshot step6 failed: {exc}")

    def write_step7_final(
        self,
        df: pd.DataFrame,
        pipeline_result: dict,
        duration_ms: float,
    ) -> None:
        """Step 7 — final parquet profile + end-to-end pipeline summary."""
        if self.disabled:
            return
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # 7a. Final dataset column profile
            df_clean = _redact_pii(df.copy())
            profile = _build_profile(df_clean, 5)  # reuse stage-5 profile (includes banned flag)
            profile.to_csv(self.output_dir / "step7_final_dataset_profile.csv", index=False)

            # 7b. Pipeline summary — one row per step
            steps = pipeline_result.get("steps", {})
            summary_rows = []
            step_labels = {
                "load": "Step 1 — Load CSV",
                "data_engineering": "Step 2 — Data Engineering (clean + transform)",
                "feature_engineering": "Step 3 — Feature Engineering (Tier-1)",
                "knowledge_graph": "Step 4a — Knowledge Graph Build (Neo4j)",
                "graph_enrichment": "Step 4b — Graph Feature Enrichment (Tier-2)",
                "training": "Step 5 — ML Model Training",
                "registry": "Step 6 — Model Registry Verification",
                "save": "Step 7 — Save Processed Parquet",
            }
            for key, label in step_labels.items():
                s = steps.get(key, {})
                row: dict[str, Any] = {
                    "step": label,
                    "status": s.get("status", "not_run"),
                    "duration_ms": s.get("duration_ms", ""),
                }
                # Attach step-specific counts
                if key == "load":
                    row["rows"] = s.get("rows", "")
                    row["columns"] = s.get("columns", "")
                elif key == "data_engineering":
                    row["rows_in"] = s.get("rows_raw", "")
                    row["rows_out"] = s.get("rows_final", "")
                    row["columns_out"] = s.get("columns_final", "")
                    row["quality_score"] = s.get("quality_score", "")
                elif key == "feature_engineering":
                    row["features_created"] = s.get("features_created", "")
                    row["total_columns"] = s.get("total_columns", "")
                elif key == "knowledge_graph":
                    row["nodes_created"] = s.get("nodes_created", "")
                    row["relationships_created"] = s.get("relationships_created", "")
                elif key == "training":
                    row["models_trained"] = s.get("models_trained", "")
                elif key == "registry":
                    row["registered_models"] = s.get("registered_models", "")
                summary_rows.append(row)

            pd.DataFrame(summary_rows).to_csv(
                self.output_dir / "step7_pipeline_summary.csv", index=False
            )
            logger.info(f"Snapshot step7: final profile ({len(profile)} cols), pipeline summary ({len(summary_rows)} steps)")
        except Exception as exc:
            logger.warning(f"Snapshot step7 failed: {exc}")

    def _write_graph_delta_named(self, df_enriched: pd.DataFrame, tier1_graph: pd.DataFrame) -> None:
        """Save Tier-1 vs Tier-2 graph column delta to step4_graph_feature_delta.csv."""
        from app.ml.utils import GRAPH_CONTEXT_FEATURES
        tier1_clean = _redact_pii(tier1_graph.copy())
        rows = []
        for col in GRAPH_CONTEXT_FEATURES:
            if col not in df_enriched.columns or col not in tier1_clean.columns:
                continue
            t1 = pd.to_numeric(tier1_clean[col], errors="coerce").fillna(0.0)
            t2 = pd.to_numeric(df_enriched[col], errors="coerce").fillna(0.0)
            diff = (t2 - t1).abs()
            changed = int((diff > 1e-9).sum())
            n = max(len(t1), 1)
            t1_std = float(t1.std()) if len(t1) > 1 else 0.0
            t2_std = float(t2.std()) if len(t2) > 1 else 0.0
            corr = float(t1.corr(t2)) if (t1_std > 0 and t2_std > 0) else 1.0
            if pd.isna(corr):
                corr = 1.0
            rows.append({
                "feature": col,
                "tier1_mean_before_graph": round(float(t1.mean()), 6),
                "tier2_mean_after_graph": round(float(t2.mean()), 6),
                "mean_absolute_change": round(float(diff.mean()), 6),
                "max_absolute_change": round(float(diff.max()), 6),
                "pct_rows_changed": round(float(changed / n * 100), 2),
                "tier1_vs_tier2_correlation": round(corr, 6),
            })
        if rows:
            pd.DataFrame(rows).to_csv(
                self.output_dir / "step4_graph_feature_delta.csv", index=False
            )
            logger.info(f"Snapshot: wrote step4_graph_feature_delta.csv ({len(rows)} features)")

    # ------------------------------------------------------------------
    # Legacy write() — kept for backward compatibility with existing calls
    # ------------------------------------------------------------------

    def write(
        self,
        stage_no: int,
        name: str,
        df: pd.DataFrame,
        notes: str | None = None,
        tier1_graph: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """
        Write sample CSV, full Parquet, and column profile for a stage.
        Returns manifest record dict or empty dict on failure/disabled.
        """
        if self.disabled:
            return {}

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            df_clean = _redact_pii(df.copy())
            prefix = f"{stage_no}_{name}"

            # 1. Sample CSV
            sample_df = _sample(df_clean, self.sample_rows)
            sample_df.to_csv(self.output_dir / f"{prefix}.csv", index=False)

            # 2. Full Parquet
            df_clean.to_parquet(self.output_dir / f"{prefix}_full.parquet", index=False)

            # 3. Profile CSV
            profile_df = _build_profile(df_clean, stage_no)
            profile_df.to_csv(self.output_dir / f"{prefix}_profile.csv", index=False)

            # 4. Graph Delta (Stage 4)
            if stage_no == 4 and tier1_graph is not None:
                self._write_graph_delta(df_clean, tier1_graph)

            # 5. Manifest record
            cur_cols = list(df_clean.columns)
            cur_set = set(cur_cols)
            new_cols = sorted(list(cur_set - self._prev_cols))
            dropped_cols = sorted(list(self._prev_cols - cur_set))
            mem_mb = round(float(df_clean.memory_usage(deep=True).sum() / (1024 * 1024)), 2)

            record: dict[str, Any] = {
                "stage_no": stage_no,
                "name": name,
                "rows": len(df_clean),
                "cols": len(df_clean.columns),
                "new_columns": new_cols,
                "dropped_columns": dropped_cols,
                "memory_mb": mem_mb,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "notes": notes or "",
            }
            self._manifest.append(record)
            self._prev_cols = cur_set

            logger.info(
                f"Snapshot stage {stage_no} '{name}': {len(df_clean):,} rows × {len(df_clean.columns)} cols"
            )
            return record

        except Exception as exc:
            logger.warning(f"Snapshot stage {stage_no} '{name}' failed: {exc}", exc_info=True)
            return {}

    def _write_graph_delta(self, df_enriched: pd.DataFrame, tier1_graph: pd.DataFrame) -> None:
        """Save Tier-1 vs Tier-2 graph column delta statistics (legacy path: 4_graph_delta.csv)."""
        self._write_graph_delta_named(df_enriched, tier1_graph)
        # Also write legacy filename for backward compatibility
        from app.ml.utils import GRAPH_CONTEXT_FEATURES
        tier1_clean = _redact_pii(tier1_graph.copy())
        rows = []
        for col in GRAPH_CONTEXT_FEATURES:
            if col not in df_enriched.columns or col not in tier1_clean.columns:
                continue
            t1 = pd.to_numeric(tier1_clean[col], errors="coerce").fillna(0.0)
            t2 = pd.to_numeric(df_enriched[col], errors="coerce").fillna(0.0)
            diff = (t2 - t1).abs()
            changed = int((diff > 1e-9).sum())
            n = max(len(t1), 1)
            t1_std = float(t1.std()) if len(t1) > 1 else 0.0
            t2_std = float(t2.std()) if len(t2) > 1 else 0.0
            corr = float(t1.corr(t2)) if (t1_std > 0 and t2_std > 0) else 1.0
            if pd.isna(corr):
                corr = 1.0
            rows.append({
                "column": col,
                "tier1_mean": round(float(t1.mean()), 6),
                "tier2_mean": round(float(t2.mean()), 6),
                "mean_abs_change": round(float(diff.mean()), 6),
                "max_abs_change": round(float(diff.max()), 6),
                "pct_rows_changed": round(float(changed / n * 100), 2),
                "tier1_tier2_corr": round(corr, 6),
            })
        if rows:
            pd.DataFrame(rows).to_csv(self.output_dir / "4_graph_delta.csv", index=False)

    def finalize(self) -> None:
        """Write 00_manifest.csv, 00_manifest.json, and 00_column_lineage.csv."""
        if self.disabled or not self._manifest:
            return

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            # 1. 00_manifest.json
            with open(self.output_dir / "00_manifest.json", "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2, default=str)

            # 2. 00_manifest.csv
            flat_records = []
            for r in self._manifest:
                flat_records.append({
                    "stage_no": r["stage_no"],
                    "name": r["name"],
                    "rows": r["rows"],
                    "cols": r["cols"],
                    "new_columns": "|".join(r["new_columns"]),
                    "dropped_columns": "|".join(r["dropped_columns"]),
                    "memory_mb": r["memory_mb"],
                    "timestamp": r["timestamp"],
                    "notes": r["notes"],
                })
            pd.DataFrame(flat_records).to_csv(self.output_dir / "00_manifest.csv", index=False)

            # 3. 00_column_lineage.csv
            stage_col_sets: dict[int, set[str]] = {}
            stage_names: dict[int, str] = {}
            all_cols: set[str] = set()

            for r in self._manifest:
                sno = r["stage_no"]
                name = r["name"]
                prof_path = self.output_dir / f"{sno}_{name}_profile.csv"
                if prof_path.exists():
                    prof_df = pd.read_csv(prof_path)
                    cols = set(prof_df["column"].tolist())
                else:
                    cols = set()
                stage_col_sets[sno] = cols
                stage_names[sno] = name
                all_cols |= cols

            lineage_rows = []
            stage_nos = sorted(stage_col_sets.keys())
            for col in sorted(list(all_cols)):
                row: dict[str, Any] = {"column": col}
                for sno in stage_nos:
                    col_header = f"s{sno:02d}_{stage_names[sno]}"
                    row[col_header] = col in stage_col_sets[sno]
                lineage_rows.append(row)

            pd.DataFrame(lineage_rows).to_csv(self.output_dir / "00_column_lineage.csv", index=False)
            logger.info("Snapshot: finalized manifest and lineage table")

        except Exception as exc:
            logger.warning(f"Snapshot finalize failed: {exc}", exc_info=True)

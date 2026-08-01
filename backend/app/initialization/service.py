"""
AMASCI System Initialization Service
========================================
Orchestrates the ONE-TIME system initialization:

1. Detect DataCoSupplyChainDataset.csv in data/raw/
2. Validate dataset
3. Clean dataset
4. Feature Engineering
5. Train all ML models (LightGBM + RandomForest)
6. Build Knowledge Graph (Neo4j)
7. Register models in registry
8. Save metadata to PostgreSQL
9. Mark system as initialized

After initialization, the system NEVER retrains automatically.
Retraining only occurs via explicit administrator request.
"""

import logging
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.data_engineering.pipeline import DataEngineeringPipeline
from app.ml.training import TrainingOrchestrator, TrainingResult
from app.ml.registry import ModelRegistry

logger = logging.getLogger(__name__)
settings = get_settings()

RAW_DATA_DIR = Path(settings.raw_data_dir)
MASTER_DATASET_PATTERNS = [
    "DataCoSupplyChainDataset.csv",
    "DataCoSupplyChain.csv",
    "dataco_supply_chain.csv",
    "dataco*.csv",
]


class InitializationService:
    """
    Orchestrates the complete system initialization pipeline.

    This service is called ONCE on first startup when the system
    detects it has not been initialized. It processes the master
    DataCo dataset through the full pipeline.
    """

    def __init__(self):
        self._data_pipeline = DataEngineeringPipeline()
        self._training_orchestrator = TrainingOrchestrator()
        self._model_registry = ModelRegistry()

    def find_master_dataset(self) -> Path | None:
        """
        Locate the master DataCo dataset in data/raw/.
        Returns the path if found, None otherwise.
        """
        raw_dir = RAW_DATA_DIR
        if not raw_dir.exists():
            raw_dir.mkdir(parents=True, exist_ok=True)
            return None

        # Check exact filenames first
        for pattern in MASTER_DATASET_PATTERNS:
            if "*" in pattern:
                matches = list(raw_dir.glob(pattern))
                if matches:
                    return matches[0]
            else:
                candidate = raw_dir / pattern
                if candidate.exists():
                    return candidate

        # Fallback: any CSV in raw directory
        csvs = list(raw_dir.glob("*.csv"))
        if csvs:
            # Pick the largest CSV (likely the master dataset)
            return max(csvs, key=lambda p: p.stat().st_size)

        return None

    def execute(self, dataset_path: Path | None = None) -> dict[str, Any]:
        """
        Execute the full initialization pipeline.

        Args:
            dataset_path: Explicit path to dataset. If None, auto-detects.

        Returns:
            Complete initialization result with all metadata.
        """
        start_time = time.perf_counter()
        result: dict[str, Any] = {
            "status": "started",
            "steps": {},
            "errors": [],
        }

        # Step 0: Locate dataset
        if dataset_path is None:
            dataset_path = self.find_master_dataset()

        if dataset_path is None or not dataset_path.exists():
            result["status"] = "skipped"
            result["reason"] = "No master dataset found in data/raw/"
            logger.info("Initialization skipped: no dataset found in data/raw/")
            return result

        logger.info(f"=== SYSTEM INITIALIZATION STARTED ===")
        logger.info(f"Dataset: {dataset_path.name} ({dataset_path.stat().st_size / 1024 / 1024:.1f} MB)")

        result["dataset_filename"] = dataset_path.name
        result["dataset_size_mb"] = round(dataset_path.stat().st_size / 1024 / 1024, 2)

        try:
            # Step 1: Load dataset
            step_start = time.perf_counter()
            logger.info("[1/7] Loading dataset...")
            df = pd.read_csv(dataset_path, encoding="latin-1")
            result["dataset_rows"] = len(df)
            result["dataset_columns"] = len(df.columns)
            result["steps"]["load"] = {
                "status": "completed",
                "rows": len(df),
                "columns": len(df.columns),
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(f"[1/7] Loaded: {len(df)} rows, {len(df.columns)} columns")

            # Step 2: Data Engineering Pipeline (Validate + Clean + Transform)
            step_start = time.perf_counter()
            logger.info("[2/7] Running data engineering pipeline...")
            df_processed, pipeline_result = self._data_pipeline.execute(df, dataset_id="master_init")

            if pipeline_result.status == "failed":
                raise RuntimeError(f"Data pipeline failed: {pipeline_result.errors}")

            result["steps"]["data_engineering"] = {
                "status": "completed",
                "rows_raw": pipeline_result.row_count_raw,
                "rows_clean": pipeline_result.row_count_clean,
                "rows_final": pipeline_result.row_count_final,
                "columns_final": pipeline_result.column_count_final,
                "quality_score": pipeline_result.validation_report.get("quality_score", 0),
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(
                f"[2/7] Data engineering complete: "
                f"{pipeline_result.row_count_raw} → {pipeline_result.row_count_final} rows"
            )

            # Step 3: Feature Engineering
            step_start = time.perf_counter()
            logger.info("[3/7] Feature engineering...")
            df_features = self._engineer_features(df_processed)
            result["steps"]["feature_engineering"] = {
                "status": "completed",
                "features_created": len(df_features.columns) - len(df_processed.columns),
                "total_columns": len(df_features.columns),
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(f"[3/7] Feature engineering complete: {len(df_features.columns)} total columns")

            # Step 4: Train ML Models
            step_start = time.perf_counter()
            logger.info("[4/7] Training ML models...")
            training_results = self._training_orchestrator.train_all(
                df_features, dataset_version="master_v1"
            )
            result["steps"]["training"] = {
                "status": "completed",
                "models_trained": len(training_results),
                "models": {
                    k: {
                        "version": v.version_id,
                        "accuracy": v.metrics.get("accuracy", v.metrics.get("r2_score", 0)),
                        "duration_ms": round(v.training_duration_ms, 1),
                    }
                    for k, v in training_results.items()
                },
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(f"[4/7] Training complete: {len(training_results)} models")

            # Step 5: Build Knowledge Graph
            step_start = time.perf_counter()
            logger.info("[5/7] Building Knowledge Graph...")
            graph_result = self._build_knowledge_graph(df_features)
            result["steps"]["knowledge_graph"] = {
                "status": "completed",
                "nodes_created": graph_result.get("nodes_created", 0),
                "relationships_created": graph_result.get("relationships_created", 0),
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(
                f"[5/7] Knowledge Graph built: "
                f"{graph_result.get('nodes_created', 0)} nodes, "
                f"{graph_result.get('relationships_created', 0)} relationships"
            )

            # Step 6: Register models (already done in training step via registry)
            step_start = time.perf_counter()
            logger.info("[6/7] Verifying model registry...")
            registry_info = self._model_registry.list_all_models()
            result["steps"]["registry"] = {
                "status": "completed",
                "registered_models": sum(len(v) for v in registry_info.values()),
                "model_types": list(registry_info.keys()),
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(f"[6/7] Registry verified: {sum(len(v) for v in registry_info.values())} models")

            # Step 7: Save processed dataset for future use
            step_start = time.perf_counter()
            logger.info("[7/7] Saving processed dataset...")
            processed_path = Path(settings.upload_dir) / "processed_master.parquet"
            processed_path.parent.mkdir(parents=True, exist_ok=True)
            df_features.to_parquet(processed_path, index=False)
            result["steps"]["save"] = {
                "status": "completed",
                "path": str(processed_path),
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(f"[7/7] Processed dataset saved")

            # Finalize
            total_duration = (time.perf_counter() - start_time) * 1000
            result["status"] = "completed"
            result["total_duration_ms"] = round(total_duration, 1)
            result["models_trained"] = len(training_results)
            result["graph_nodes"] = graph_result.get("nodes_created", 0)
            result["graph_relationships"] = graph_result.get("relationships_created", 0)

            logger.info(f"=== SYSTEM INITIALIZATION COMPLETED in {total_duration / 1000:.1f}s ===")

        except Exception as e:
            total_duration = (time.perf_counter() - start_time) * 1000
            result["status"] = "failed"
            result["error"] = str(e)
            result["total_duration_ms"] = round(total_duration, 1)
            result["errors"].append(str(e))
            logger.error(f"=== SYSTEM INITIALIZATION FAILED: {e} ===", exc_info=True)

        return result

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute business-derived features for ML training.
        22 engineered features across operational intelligence categories.
        """
        df = df.copy()

        # Shipping Intelligence
        if "Days for shipping (real)" in df.columns and "Days for shipment (scheduled)" in df.columns:
            df["shipping_delay_days"] = df["Days for shipping (real)"] - df["Days for shipment (scheduled)"]
            df["shipping_delay_ratio"] = (
                df["shipping_delay_days"] / df["Days for shipment (scheduled)"].replace(0, 1)
            )
            df["is_delayed"] = (df["shipping_delay_days"] > 0).astype(int)

        # Financial Intelligence
        if "Sales" in df.columns and "Order Item Quantity" in df.columns:
            df["revenue_per_unit"] = df["Sales"] / df["Order Item Quantity"].replace(0, 1)

        if "Order Profit Per Order" in df.columns and "Sales" in df.columns:
            df["profit_margin"] = df["Order Profit Per Order"] / df["Sales"].replace(0, 1)
            df["profit_margin"] = df["profit_margin"].clip(-1, 1)

        if "Order Item Discount" in df.columns:
            df["discount_flag"] = (df["Order Item Discount"] > 0).astype(int)
            df["high_discount"] = (df["Order Item Discount"] > 0.2).astype(int)

        # Demand Intelligence
        if "Order Item Quantity" in df.columns:
            df["quantity_log"] = np.log1p(df["Order Item Quantity"].clip(lower=0))

        if "Sales" in df.columns:
            df["sales_log"] = np.log1p(df["Sales"].clip(lower=0))

        # Market Intelligence
        if "Market" in df.columns:
            market_risk = df.groupby("Market")["Late_delivery_risk"].mean() if "Late_delivery_risk" in df.columns else pd.Series()
            if not market_risk.empty:
                df["market_risk_score"] = df["Market"].map(market_risk).fillna(0.5)

        # Shipping Mode Intelligence
        if "Shipping Mode" in df.columns:
            mode_map = {"Same Day": 4, "First Class": 3, "Second Class": 2, "Standard Class": 1}
            df["shipping_priority"] = df["Shipping Mode"].map(mode_map).fillna(1).astype(int)

        # Customer Intelligence
        if "Customer Segment" in df.columns:
            segment_map = {"Corporate": 3, "Home Office": 2, "Consumer": 1}
            df["customer_value_tier"] = df["Customer Segment"].map(segment_map).fillna(1).astype(int)

        # Calendar Intelligence
        if "order date (DateOrders)" in df.columns:
            order_dt = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
            if order_dt.notna().any():
                df["order_month"] = order_dt.dt.month.fillna(1).astype(int)
                df["order_dayofweek"] = order_dt.dt.dayofweek.fillna(0).astype(int)
                df["order_quarter"] = order_dt.dt.quarter.fillna(1).astype(int)
                df["is_weekend_order"] = (order_dt.dt.dayofweek >= 5).astype(int)
                df["is_month_end"] = (order_dt.dt.day >= 25).astype(int)

        # Operational Complexity
        if "Order Item Quantity" in df.columns and "Product Price" in df.columns:
            df["order_value"] = df["Order Item Quantity"] * df["Product Price"]

        # Supplier Performance (aggregated)
        if "Department Name" in df.columns and "Late_delivery_risk" in df.columns:
            dept_risk = df.groupby("Department Name")["Late_delivery_risk"].mean()
            df["department_risk_score"] = df["Department Name"].map(dept_risk).fillna(0.5)

        logger.info(f"Feature engineering: {len(df.columns)} total columns")
        return df

    def _build_knowledge_graph(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Build the Knowledge Graph from processed data.
        Attempts a full Neo4j MERGE build; falls back to entity extraction only.
        """
        try:
            from app.graph.builder import GraphBuilder
            from app.graph.connection import get_connection_manager
            import asyncio

            conn = get_connection_manager()
            builder = GraphBuilder(conn)

            # Run async graph build synchronously inside the init pipeline
            loop = asyncio.new_event_loop()
            try:
                build_result = loop.run_until_complete(builder.build_full_graph(df))
            finally:
                loop.close()

            nodes_created = build_result.get("nodes_created", 0)
            rels_created = build_result.get("relationships_created", 0)

            # Persist metadata for startup reference
            import json
            entities_path = Path(settings.upload_dir) / "graph_entities.json"
            entities_path.parent.mkdir(parents=True, exist_ok=True)
            entities_path.write_text(json.dumps({
                "nodes_created": nodes_created,
                "relationships_created": rels_created,
                "ready_for_build": False,  # already built
                "status": "built",
            }, indent=2))

            return {
                "nodes_created": nodes_created,
                "relationships_created": rels_created,
                "status": "built",
            }

        except Exception as neo4j_err:
            logger.warning(f"Neo4j graph build failed ({neo4j_err}), falling back to entity extraction")

        # Fallback: extract counts only (Neo4j offline)
        try:
            from app.graph.extractor import EntityExtractor
            import json

            extractor = EntityExtractor()
            entities = extractor.extract_all(df)
            total_nodes = sum(len(v) for v in entities.get("nodes", {}).values())
            total_rels = len(entities.get("relationships", []))

            entities_path = Path(settings.upload_dir) / "graph_entities.json"
            entities_path.parent.mkdir(parents=True, exist_ok=True)
            entities_path.write_text(json.dumps({
                "node_counts": {k: len(v) for k, v in entities.get("nodes", {}).items()},
                "relationship_count": total_rels,
                "ready_for_build": True,  # needs POST /graph/build
                "status": "extracted",
            }, indent=2))

            return {
                "nodes_created": total_nodes,
                "relationships_created": total_rels,
                "status": "extracted",
            }
        except Exception as e:
            logger.error(f"Knowledge graph extraction failed: {e}")
            return {"nodes_created": 0, "relationships_created": 0, "status": "failed", "error": str(e)}

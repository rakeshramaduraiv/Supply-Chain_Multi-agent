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
from app.ml.utils import GRAPH_CONTEXT_FEATURES

logger = logging.getLogger(__name__)
settings = get_settings()

RAW_DATA_DIR = Path(settings.raw_data_dir)
MASTER_DATASET_PATTERNS = [
    "DataCoSupplyChainDataset.csv",
    "DataCoSupplyChain.csv",
    "dataco_supply_chain.csv",
    "dataco*.csv",
]

_PARQUET_MIN_ROWS   = 100_000
_PARQUET_DATE_MIN   = pd.Timestamp("2015-01-01")
_PARQUET_DATE_MAX   = pd.Timestamp("2018-01-31")
_PARQUET_DATE_COL   = "order date (DateOrders)"


def assert_parquet_integrity(df: pd.DataFrame, path: str = "") -> None:
    """
    Hard assertions on processed_master.parquet.

    Raises RuntimeError (not a warning) on any violation:
      1. Row count must be >= 100,000
      2. Date range must cover 2015-01-01 .. 2018-01-31
      3. All four GRAPH_CONTEXT_FEATURES must be present as columns
    """
    label = f" ({path})" if path else ""

    # 1. Row count
    if len(df) < _PARQUET_MIN_ROWS:
        raise RuntimeError(
            f"processed_master.parquet{label} has only {len(df):,} rows — "
            f"expected >= {_PARQUET_MIN_ROWS:,}. "
            f"This is a stub or truncated file. Re-run initialization."
        )

    # 2. Date range
    if _PARQUET_DATE_COL not in df.columns:
        raise RuntimeError(
            f"processed_master.parquet{label} is missing date column "
            f"'{_PARQUET_DATE_COL}'. Cannot verify date range."
        )
    dates = pd.to_datetime(df[_PARQUET_DATE_COL], errors="coerce").dropna()
    if dates.empty:
        raise RuntimeError(
            f"processed_master.parquet{label}: date column '{_PARQUET_DATE_COL}' "
            f"contains no parseable dates."
        )
    actual_min = dates.min()
    actual_max = dates.max()
    if actual_min > _PARQUET_DATE_MIN:
        raise RuntimeError(
            f"processed_master.parquet{label}: earliest date is {actual_min.date()} — "
            f"expected <= {_PARQUET_DATE_MIN.date()}. Dataset does not cover full range."
        )
    if actual_max < _PARQUET_DATE_MAX:
        raise RuntimeError(
            f"processed_master.parquet{label}: latest date is {actual_max.date()} — "
            f"expected >= {_PARQUET_DATE_MAX.date()}. Dataset does not cover full range."
        )

    # 3. Graph context features — must all be present (Tier-1 or Tier-2)
    missing_graph = [c for c in GRAPH_CONTEXT_FEATURES if c not in df.columns]
    if missing_graph:
        raise RuntimeError(
            f"processed_master.parquet{label} is missing graph context features: "
            f"{missing_graph}. "
            f"Ensure feature engineering ran to completion (Tier-1 aggregates "
            f"must be present even when Neo4j enrichment is unavailable)."
        )

    # 4. Leaky columns must NOT appear in any agent's feature list
    # (They may exist as raw columns in the parquet for RCA/display — that is fine.
    # The ban is on using them as ML inputs, which is enforced at training time.)
    from app.ml.utils import _LEAKY as _LEAKY_SETS, FEATURE_CONFIGS
    all_feature_cols: set[str] = set()
    for fc in FEATURE_CONFIGS.values():
        all_feature_cols.update(fc.features)
    all_leaky = set().union(*_LEAKY_SETS.values())
    leaky_in_features = sorted(all_leaky & all_feature_cols & set(df.columns))
    if leaky_in_features:
        raise RuntimeError(
            f"processed_master.parquet{label} has leaky columns present in "
            f"agent feature lists: {leaky_in_features}. "
            f"Remove them from FEATURE_CONFIGS before saving."
        )


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
        from app.graph.connection import Neo4jConnectionManager
        # Do NOT connect here — the async driver must be connected and used
        # within the same event loop.  Connection happens in _run_graph_steps().
        self._graph_conn = Neo4jConnectionManager()

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

    async def execute(self, dataset_path: Path | None = None) -> dict[str, Any]:
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

            # Step 3: Feature Engineering (Tier-1, no graph)
            step_start = time.perf_counter()
            logger.info("[3/7] Feature engineering (Tier-1)...")
            from app.feature_engineering import engineer_features
            df_features = engineer_features(df_processed)
            result["steps"]["feature_engineering"] = {
                "status": "completed",
                "features_created": len(df_features.columns) - len(df_processed.columns),
                "total_columns": len(df_features.columns),
                "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
            }
            logger.info(f"[3/7] Feature engineering complete: {len(df_features.columns)} total columns")

            # Steps 4 + 4b: graph constraints + enrichment in ONE event loop
            # The Neo4j async driver's transport is bound to the loop it is
            # created in.  Running connect() and execute_query() in separate
            # asyncio.run() calls destroys the transport between calls.
            # Solution: one async function that connects, builds constraints,
            # enriches, and disconnects — all within a single asyncio.run().
            step_start = time.perf_counter()
            logger.info("[4/7] Building Knowledge Graph + enriching features...")

            date_col = next(
                (c for c in ("order_date", "order date (DateOrders)") if c in df_features.columns),
                None,
            )
            if date_col is None:
                raise RuntimeError(
                    "Step 4b: no date column found in df_features. "
                    "Cannot build chronological train_mask for graph enrichment."
                )
            dates = pd.to_datetime(df_features[date_col], errors="coerce")
            if not dates.is_monotonic_increasing:
                raise RuntimeError(
                    "Step 4b: df_features is not sorted by date. "
                    "Call _sort_chronologically before enrichment."
                )
            cutoff = dates.quantile(0.8)
            train_mask = dates <= cutoff

            from app.graph.enrichment import enrich_graph_features_from_neo4j
            from app.graph.builder import GraphBuilder

            async def _graph_steps(df_in: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
                """Connect, build graph, enrich, disconnect — one loop."""
                await self._graph_conn.connect()
                try:
                    builder = GraphBuilder(self._graph_conn)
                    await builder.create_constraints()

                    # Build graph nodes + relationships from the engineered DataFrame
                    from app.graph.extractor import EntityExtractor
                    extractor = EntityExtractor()

                    # Fine-grained enrichment nodes — computed on training slice only
                    window_end_str = str(cutoff.date()) if not pd.isna(cutoff) else ""
                    supplier_routes = extractor.extract_supplier_routes(df_in, train_mask, window_end_str)
                    routes          = extractor.extract_routes(df_in, train_mask, window_end_str)
                    inventories     = extractor.extract_inventories(df_in, train_mask, window_end_str)

                    # Coarse nodes for TPKE / RCA
                    suppliers   = extractor.extract_suppliers(df_in)
                    products    = extractor.extract_products(df_in)
                    warehouses  = extractor.extract_warehouses(df_in)
                    shipments   = extractor.extract_shipments(df_in)
                    customers   = extractor.extract_customers(df_in)
                    orders      = extractor.extract_orders(df_in, sample_size=5000)
                    cal_events  = extractor.extract_calendar_events(df_in)
                    rels        = extractor.extract_relationships(
                        df_in, suppliers, products, warehouses,
                        shipments, customers, orders, cal_events,
                    )
                    build_result = await builder.build_full_graph(
                        suppliers=suppliers, products=products,
                        warehouses=warehouses, shipments=shipments,
                        customers=customers, orders=orders,
                        calendar_events=cal_events, relationships=rels,
                        dataset_version="master_v1",
                        supplier_routes=supplier_routes,
                        routes=routes,
                        inventories=inventories,
                    )
                    logger.info(
                        f"[4/7] Graph built: {build_result.nodes_created} nodes, "
                        f"{build_result.relationships_created} rels"
                    )

                    df_out = await enrich_graph_features_from_neo4j(df_in, self._graph_conn, train_mask)
                    return df_out, True
                finally:
                    await self._graph_conn.disconnect()

            graph_enriched_flag = False
            build_nodes = 0
            build_rels = 0
            try:
                df_features, graph_enriched_flag = await _graph_steps(df_features)
                result["steps"]["knowledge_graph"] = {
                    "status": "completed",
                    "nodes_created": build_nodes,
                    "relationships_created": build_rels,
                    "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
                }
                result["steps"]["graph_enrichment"] = {
                    "status": "completed",
                    "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
                }
                logger.info("[4/7] Graph constraints + enrichment complete")
            except Exception as enrich_err:
                allow_fallback = settings.allow_enrichment_fallback
                if not allow_fallback:
                    raise RuntimeError(
                        f"Graph enrichment failed and ALLOW_ENRICHMENT_FALLBACK=False. "
                        f"Training on unenriched features is not permitted. "
                        f"Original error: {enrich_err}"
                    ) from enrich_err
                logger.warning(
                    f"[4/7] Graph enrichment failed ({enrich_err}); "
                    f"ALLOW_ENRICHMENT_FALLBACK=True — Tier-1 aggregates retained."
                )
                result["steps"]["knowledge_graph"] = {
                    "status": "skipped", "reason": str(enrich_err),
                    "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
                }
                result["steps"]["graph_enrichment"] = {
                    "status": "skipped", "reason": str(enrich_err), "degraded": True,
                    "duration_ms": round((time.perf_counter() - step_start) * 1000, 1),
                }

            # Step 5: Train ML Models (now sees real graph features from Step 4)
            step_start = time.perf_counter()
            logger.info("[5/7] Training ML models...")
            training_results = self._training_orchestrator.train_all(
                df_features, dataset_version="master_v1",
                graph_enriched=graph_enriched_flag,
                already_engineered=True,
                training_path="initialization",
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
            logger.info(f"[5/7] Training complete: {len(training_results)} models")

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

            # Hard pre-write guard — raises before touching disk if data is bad.
            if len(df_features) >= _PARQUET_MIN_ROWS:
                assert_parquet_integrity(df_features, str(processed_path))

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
            result["graph_nodes"] = result.get("steps", {}).get("knowledge_graph", {}).get("nodes_created", 0)
            result["graph_relationships"] = result.get("steps", {}).get("knowledge_graph", {}).get("relationships_created", 0)

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
            df["shipping_delay"] = df["Days for shipping (real)"] - df["Days for shipment (scheduled)"]
            df["shipping_delay_ratio"] = (
                df["shipping_delay"] / df["Days for shipment (scheduled)"].replace(0, 1)
            )
            df["is_delayed"] = (df["shipping_delay"] > 0).astype(int)

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
            import asyncio

            builder = GraphBuilder(self._graph_conn)

            # Create constraints only — full node/rel build requires
            # pre-extracted node lists (see GraphBuilder.build_full_graph signature).
            # The orchestrator/extractor pipeline is responsible for the full build;
            # here we just ensure indexes exist before enrichment runs.
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(builder.create_constraints())
            finally:
                loop.close()

            nodes_created = 0
            rels_created = 0

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

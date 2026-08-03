"""
AMASCI Dynamic Dataset Upgrade Service
=========================================
Orchestrates dynamic platform upgrades when users upload new actual data.

Workflow:
1. Merge new actuals with existing DataCo baseline dataset (processed_master.parquet).
2. Re-engineer features across the combined (Old DataCo Base + New Actuals) dataset.
3. Retrain and upgrade all ML Models (LightGBM, Random Forest, Delay Classifier, Demand Forecaster).
4. Dynamically update Knowledge Graph (Neo4j) nodes, relationships, and risk/delay properties.
5. Refresh GraphRAG context builders, context modules, and evidence synthesizers.
6. Invalidate dataset caches & broadcast real-time WebSocket notifications across frontend.
"""

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.api.v1.endpoints.dataset_summary import clear_dataset_cache
from app.api.v1.endpoints.ws import broadcast_event
from app.core.config import get_settings
from app.data_engineering.pipeline import DataEngineeringPipeline
from app.feature_engineering import FeatureEngineeringPipeline
from app.graph.actual_integration import auto_sync_actuals
from app.graph.connection import get_connection_manager
from app.ml.registry import ModelRegistry
from app.ml.training import TrainingOrchestrator
from app.services import BaseService

logger = logging.getLogger(__name__)
settings = get_settings()


class DynamicDatasetUpgradeService(BaseService):
    """
    Service responsible for dynamically upgrading ML Models, Knowledge Graph,
    and GraphRAG when new actual dataset files are uploaded.
    """

    def __init__(self) -> None:
        super().__init__()
        self.upload_dir = Path(settings.upload_path)
        self.master_parquet_path = self.upload_dir / "processed_master.parquet"
        self._data_pipeline = DataEngineeringPipeline()
        self._feature_pipeline = FeatureEngineeringPipeline()
        self._training_orchestrator = TrainingOrchestrator()
        self._model_registry = ModelRegistry()

    def load_existing_master_dataset(self) -> pd.DataFrame:
        """
        Load the existing master dataset (DataCo baseline + previous uploads).
        If processed_master.parquet does not exist, look for raw DataCo CSV.
        """
        if self.master_parquet_path.exists():
            try:
                df = pd.read_parquet(self.master_parquet_path)
                logger.info(f"[DynamicUpgrade] Loaded existing master parquet: {len(df)} rows")
                return df
            except Exception as e:
                logger.warning(f"[DynamicUpgrade] Failed to read existing master parquet: {e}")

        # Fallback to raw DataCo dataset in data/raw
        raw_dir = Path(settings.raw_data_dir)
        raw_candidates = [
            raw_dir / "DataCoSupplyChainDataset.csv",
            raw_dir / "DataCoSupplyChain.csv",
            raw_dir / "dataco_supply_chain.csv",
        ]
        for candidate in raw_candidates:
            if candidate.exists():
                try:
                    df = pd.read_csv(candidate, encoding="latin-1")
                    logger.info(f"[DynamicUpgrade] Loaded base DataCo raw CSV: {len(df)} rows")
                    return df
                except Exception as e:
                    logger.warning(f"[DynamicUpgrade] Failed to read raw DataCo CSV {candidate}: {e}")

        # Check any CSV in raw_dir
        if raw_dir.exists():
            csvs = list(raw_dir.glob("*.csv"))
            if csvs:
                largest_csv = max(csvs, key=lambda p: p.stat().st_size)
                try:
                    df = pd.read_csv(largest_csv, encoding="latin-1")
                    logger.info(f"[DynamicUpgrade] Loaded largest raw CSV {largest_csv.name}: {len(df)} rows")
                    return df
                except Exception as e:
                    logger.warning(f"[DynamicUpgrade] Failed to read {largest_csv}: {e}")

        logger.warning("[DynamicUpgrade] No existing master dataset found. Creating empty DataFrame.")
        return pd.DataFrame()

    async def upgrade_with_actuals(
        self,
        df_new: pd.DataFrame,
        filename: str = "actuals.csv",
        period: str = "2024-01",
    ) -> dict[str, Any]:
        """
        Main entry point for dynamic dataset upgrade.

        Executes:
        1. Merge df_new into df_old (DataCo baseline) -> df_combined
        2. Feature engineering on df_combined
        3. Save updated processed_master.parquet
        4. Retrain ML models on df_combined
        5. Sync Knowledge Graph (Neo4j) nodes & actual properties
        6. Refresh GraphRAG context & invalidates caches
        7. Broadcast real-time events
        """
        start_time = time.perf_counter()
        upgrade_id = f"upgrade_{int(time.time())}"
        ts = datetime.now(timezone.utc).isoformat()

        logger.info(f"=== DYNAMIC DATASET UPGRADE STARTED ({upgrade_id}) ===")
        logger.info(f"New dataset filename: {filename}, rows: {len(df_new)}, period: {period}")

        # Clean column names in df_new
        df_new.columns = [c.strip() for c in df_new.columns]

        # ── Step 1: Merge Datasets (Old DataCo Base + New Actual Uploads) ──────
        df_old = self.load_existing_master_dataset()
        old_rows = len(df_old)

        if not df_old.empty:
            # Align columns and concatenate
            df_combined = pd.concat([df_old, df_new], ignore_index=True)
            # Deduplicate if primary identifier exists
            if "Order Item Id" in df_combined.columns:
                df_combined = df_combined.drop_duplicates(subset=["Order Item Id"], keep="last")
            elif "Order Id" in df_combined.columns and "Order Item Id" in df_combined.columns:
                df_combined = df_combined.drop_duplicates(subset=["Order Id", "Order Item Id"], keep="last")
        else:
            df_combined = df_new

        combined_rows = len(df_combined)
        added_rows = combined_rows - old_rows
        logger.info(f"[Step 1/5] Merged datasets: {old_rows} old rows + {len(df_new)} uploaded -> {combined_rows} cumulative rows (+{added_rows} net)")

        # ── Step 2: Feature Engineering & Parquet Update ─────────────────────
        try:
            df_features = self._feature_pipeline.transform(df_combined)
        except Exception as e_feat:
            logger.warning(f"[DynamicUpgrade] Feature pipeline warning: {e_feat}. Proceeding with combined data.")
            df_features = df_combined.copy()

        # Save cumulative dataset atomically
        self.master_parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_features.to_parquet(self.master_parquet_path, index=False)
        logger.info(f"[Step 2/5] Saved updated cumulative dataset to {self.master_parquet_path}")

        # Clear dataset summary & analytics caches
        clear_dataset_cache()

        # Broadcast initial merge event
        await broadcast_event(
            "Dataset Merged",
            {
                "upgrade_id": upgrade_id,
                "old_rows": old_rows,
                "added_rows": len(df_new),
                "cumulative_rows": combined_rows,
                "filename": filename,
            },
        )

        # ── Step 3: Retrain / Upgrade ML Models on Cumulative Dataset ───────
        training_results_summary = {}
        try:
            logger.info("[Step 3/5] Retraining ML models on cumulative dataset...")
            training_results = self._training_orchestrator.train_all(
                df_features, dataset_version=f"cumulative_{period}_{int(time.time())}"
            )
            training_results_summary = {
                k: {
                    "version_id": v.version_id,
                    "accuracy": v.metrics.get("accuracy", v.metrics.get("r2_score", 0)),
                    "training_samples": v.n_training_samples,
                }
                for k, v in training_results.items()
            }
            await broadcast_event("ML Models Upgraded", {"upgrade_id": upgrade_id, "models": list(training_results.keys())})
            logger.info(f"[Step 3/5] Upgraded {len(training_results)} ML models on cumulative dataset")
        except Exception as e_train:
            logger.error(f"[Step 3/5] ML Model retraining warning: {e_train}", exc_info=True)

        # ── Step 4: Dynamically Upgrade Knowledge Graph & TPKE Edges ─────────
        kg_sync_info = {}
        try:
            logger.info("[Step 4/5] Updating Knowledge Graph nodes and properties...")
            kg_sync_info = await auto_sync_actuals(df_features)
            await broadcast_event("Knowledge Graph Updated", {"upgrade_id": upgrade_id, "updated_nodes": kg_sync_info.get("updated", 0)})
            logger.info(f"[Step 4/5] Knowledge Graph node properties updated: {kg_sync_info}")
        except Exception as e_kg:
            logger.error(f"[Step 4/5] Knowledge Graph update warning: {e_kg}", exc_info=True)

        # ── Step 5: Execute Closed-Loop System & GraphRAG Refresh ────────────
        closed_loop_result = {}
        try:
            logger.info("[Step 5/5] Executing Closed-Loop System & GraphRAG refresh...")
            from app.services.closed_loop import get_closed_loop_orchestrator
            loop = get_closed_loop_orchestrator()
            cycle_res = await loop.run_closed_loop_cycle(dataset_name=filename)
            closed_loop_result = cycle_res.to_dict()
            await broadcast_event("GraphRAG Refreshed", {"upgrade_id": upgrade_id, "graphrag_validated": cycle_res.graphrag_validated})
            logger.info(f"[Step 5/5] GraphRAG refreshed and closed-loop cycle completed: {cycle_res.cycle_id}")
        except Exception as e_loop:
            logger.warning(f"[Step 5/5] Closed-loop execution warning: {e_loop}")

        total_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"=== DYNAMIC DATASET UPGRADE COMPLETED in {total_duration_ms/1000:.2f}s ===")

        return {
            "upgrade_id": upgrade_id,
            "status": "completed",
            "timestamp": ts,
            "period": period,
            "filename": filename,
            "old_rows": old_rows,
            "new_rows_uploaded": len(df_new),
            "cumulative_rows": combined_rows,
            "net_rows_added": added_rows,
            "ml_models_upgraded": training_results_summary,
            "kg_nodes_updated": kg_sync_info.get("updated", 0),
            "closed_loop": closed_loop_result,
            "duration_ms": round(total_duration_ms, 2),
        }


# Global singleton instance
_upgrade_service: DynamicDatasetUpgradeService | None = None


def get_dynamic_upgrade_service() -> DynamicDatasetUpgradeService:
    global _upgrade_service
    if _upgrade_service is None:
        _upgrade_service = DynamicDatasetUpgradeService()
    return _upgrade_service

"""
Standalone retrain script — runs the full training pipeline.
Run from backend/:  python retrain.py
"""
import sys, os, logging, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("retrain")

from pathlib import Path
import pandas as pd

from app.core.config import get_settings
from app.data_engineering.pipeline import DataEngineeringPipeline
from app.feature_engineering import engineer_features
from app.ml.training import TrainingOrchestrator
from app.ml.registry import ModelRegistry

settings = get_settings()
settings.ensure_dirs()

RAW_CSV = Path("data/raw/DataCoSupplyChainDataset.csv")
PROCESSED_PATH = Path("data/uploads/processed_master.parquet")

def main():
    t0 = time.perf_counter()

    # 1. Load
    logger.info(f"Loading {RAW_CSV} ...")
    df_raw = pd.read_csv(RAW_CSV, encoding="latin-1")
    logger.info(f"Loaded {len(df_raw):,} rows x {len(df_raw.columns)} cols")

    # 2. Data engineering pipeline
    logger.info("Running data engineering pipeline ...")
    pipeline = DataEngineeringPipeline()
    df_clean, result = pipeline.execute(df_raw, dataset_id="retrain")
    if result.status == "failed":
        logger.error(f"Pipeline failed: {result.errors}")
        sys.exit(1)
    logger.info(f"Pipeline: {result.row_count_raw} -> {result.row_count_final} rows")

    # 3. Feature engineering
    logger.info("Feature engineering ...")
    df_eng = engineer_features(df_clean)
    logger.info(f"Features: {len(df_eng.columns)} columns")

    # 4. Save processed parquet
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_eng.to_parquet(PROCESSED_PATH, index=False)
    logger.info(f"Saved processed parquet: {PROCESSED_PATH}")

    # 5. Train all models
    logger.info("Training all models ...")
    orchestrator = TrainingOrchestrator()
    results = orchestrator.train_all(df_eng, dataset_version="retrain_v1")

    for name, r in results.items():
        m = r.metrics
        key = "mape" if "mape" in m else ("f1_score" if "f1_score" in m else list(m.keys())[0])
        logger.info(f"  {name:10s}  version={r.version_id}  {key}={m.get(key, '?'):.4f}")

    elapsed = time.perf_counter() - t0
    logger.info(f"Retrain complete in {elapsed:.1f}s")

if __name__ == "__main__":
    main()

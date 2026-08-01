"""
generate_monthly_synthetic_uploads.py
======================================
Generates and maintains the 12 monthly synthetic input CSV files in:
  backend/data/monthly_synthetic_uploads/

These files form a continuous monthly sequence starting directly after the
training baseline cutoff of 2017.12 (December 2017):
  - synthetic_2018-01.csv (Jan 2018, extracted from DataCo 2018-01 records)
  - synthetic_2018-02.csv (Feb 2018)
  - synthetic_2018-03.csv (Mar 2018)
  ...
  - synthetic_2018-12.csv (Dec 2018)

Run:
  python backend/scripts/generate_monthly_synthetic_uploads.py
"""

import os
import shutil
import logging
from pathlib import Path
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DATASET_PATH = BASE_DIR / "data" / "raw" / "DataCoSupplyChainDataset.csv"
SYNTHETIC_DIR = BASE_DIR / "data" / "monthly_synthetic_uploads"
FRONTEND_SAMPLE_DIR = BASE_DIR.parent / "frontend" / "public" / "sample_actuals"


def main():
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    if FRONTEND_SAMPLE_DIR.exists():
        FRONTEND_SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    if not RAW_DATASET_PATH.exists():
        logger.error(f"Master dataset not found at {RAW_DATASET_PATH}")
        return

    logger.info(f"Loading master dataset from {RAW_DATASET_PATH}...")
    df_master = pd.read_csv(RAW_DATASET_PATH, encoding="ISO-8859-1")
    df_master["order_datetime"] = pd.to_datetime(df_master["order date (DateOrders)"])

    # 1. Extract 2018-01 data directly from master dataset
    df_2018_01 = df_master[
        (df_master["order_datetime"] >= "2018-01-01") & (df_master["order_datetime"] <= "2018-01-31 23:59:59")
    ].drop(columns=["order_datetime"])

    logger.info(f"Extracted {len(df_2018_01)} rows for 2018-01 from master dataset.")

    # Save synthetic_2018-01.csv
    file_2018_01 = SYNTHETIC_DIR / "synthetic_2018-01.csv"
    df_2018_01.to_csv(file_2018_01, index=False, encoding="utf-8")
    logger.info(f"Saved {file_2018_01}")

    # 2. Check & adjust 2018-02 through 2018-12
    # If existing synthetic_2018-02..12 exist, keep them or refine them if needed
    # Baseline columns pattern from df_master
    base_columns = [c for c in df_master.columns if c != "order_datetime"]

    # Sample reference pool from 2017 data to generate synthetic future months if needed
    df_sample_pool = df_master[
        (df_master["order_datetime"] >= "2017-01-01") & (df_master["order_datetime"] <= "2017-12-31")
    ].copy()

    for month_num in range(2, 13):
        month_str = f"{month_num:02d}"
        file_name = f"synthetic_2018-{month_str}.csv"
        target_path = SYNTHETIC_DIR / file_name

        if target_path.exists():
            logger.info(f"File {file_name} already exists ({target_path.stat().st_size} bytes).")
        else:
            # Generate synthetic file for 2018-MM from sample pool
            logger.info(f"Generating synthetic file {file_name}...")
            # Sample ~2100 records
            sampled = df_sample_pool.sample(n=2100, replace=True, random_state=42 + month_num).copy()

            # Update dates to 2018-MM
            days_in_month = pd.Period(f"2018-{month_str}").days_in_month
            random_days = np.random.randint(1, days_in_month + 1, size=len(sampled))
            random_hours = np.random.randint(0, 24, size=len(sampled))
            random_mins = np.random.randint(0, 60, size=len(sampled))

            new_dates = [
                f"{month_num}/{d}/2018 {h:02d}:{m:02d}"
                for d, h, m in zip(random_days, random_hours, random_mins)
            ]
            sampled["order date (DateOrders)"] = new_dates
            sampled["shipping date (DateOrders)"] = new_dates  # simplistic shipping date update

            sampled[base_columns].to_csv(target_path, index=False, encoding="utf-8")
            logger.info(f"Generated and saved {file_name}")

    # Remove synthetic_2019-01.csv if present to maintain strictly 2018-01 to 2018-12
    file_2019_01 = SYNTHETIC_DIR / "synthetic_2019-01.csv"
    if file_2019_01.exists():
        file_2019_01.unlink()
        logger.info(f"Removed redundant {file_2019_01.name}")

    # 3. Synchronize with frontend/public/sample_actuals
    if FRONTEND_SAMPLE_DIR.exists():
        logger.info("Synchronizing synthetic CSVs to frontend/public/sample_actuals...")
        for month_num in range(1, 13):
            m_str = f"{month_num:02d}"
            src_file = SYNTHETIC_DIR / f"synthetic_2018-{m_str}.csv"
            if src_file.exists():
                dst_file1 = FRONTEND_SAMPLE_DIR / f"synthetic_2018-{m_str}.csv"
                dst_file2 = FRONTEND_SAMPLE_DIR / f"2018_{m_str}_Actual.csv"
                shutil.copy2(src_file, dst_file1)
                shutil.copy2(src_file, dst_file2)

    all_files = sorted(list(SYNTHETIC_DIR.glob("synthetic_2018-*.csv")))
    logger.info("Current continuous synthetic uploads in backend/data/monthly_synthetic_uploads:")
    for f in all_files:
        logger.info(f"  - {f.name} ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

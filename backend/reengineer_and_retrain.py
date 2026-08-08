"""
Re-engineer from raw CSV (not parquet) and retrain all agents.
This is required after A6 because the parquet has pre-computed rolling features.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import logging
logging.basicConfig(level=logging.WARNING)

import pandas as pd
from app.feature_engineering import engineer_features
from app.ml.training import TrainingOrchestrator, BaseTrainer
from app.ml.utils import IntelligenceType, TautologicalTargetError

RAW_CSV = pathlib.Path("data/raw/DataCoSupplyChainDataset.csv")
OUT_PARQUET = pathlib.Path("data/uploads/processed_master.parquet")

print(f"Loading raw CSV: {RAW_CSV}")
df_raw = pd.read_csv(RAW_CSV, encoding="latin-1")
print(f"  {len(df_raw)} rows, {len(df_raw.columns)} columns")

print("Engineering features from scratch...")
df_eng = engineer_features(df_raw)
print(f"  {len(df_eng.columns)} columns after engineering")

# Verify rolling features are now shifted (spot check)
qty_col = "Order Item Quantity"
if qty_col in df_raw.columns and "qty_roll_7" in df_eng.columns:
    # First row's qty_roll_7 should be NaN/filled (not equal to first row's qty)
    first_qty = df_raw.iloc[0][qty_col]
    first_roll = df_eng.iloc[0]["qty_roll_7"]
    print(f"  Spot check: first row qty={first_qty}, qty_roll_7={first_roll:.4f}")
    print(f"  (If equal, shift is not working; if different, shift is correct)")

print(f"\nSaving re-engineered parquet to {OUT_PARQUET}...")
df_eng.to_parquet(OUT_PARQUET, index=False)
print("  Saved.")

print("\nRetraining all agents on re-engineered data...")
orch = TrainingOrchestrator()
results = orch.train_all(df_eng, dataset_version="a6_fixed_v1")

print("\n=== RESULTS ===")
for agent, r in results.items():
    m = r.metrics
    if r.task == "classification":
        auc = m.get("roc_auc", "n/a")
        f1  = m.get("f1_score", "n/a")
        status = ""
        if isinstance(auc, float):
            if auc > 0.85:
                status = " WARN: >0.85"
            elif auc < 0.55:
                status = " WARN: <0.55"
            else:
                status = " PASS"
        print(f"  {agent}: AUC={auc}  F1={f1}{status}")
    else:
        r2   = m.get("r2", m.get("r2_score", "n/a"))
        mape = m.get("mape", "n/a")
        rmse = m.get("rmse", "n/a")
        status = ""
        if isinstance(r2, float):
            if r2 > 0.75:
                status = " WARN: R2>0.75 — possible residual leak"
            elif r2 < 0.15:
                status = " WARN: R2<0.15 — very low signal"
            else:
                status = " PASS"
        print(f"  {agent}: R2={r2}  MAPE={mape}  RMSE={rmse}{status}")
        if isinstance(r2, float) and r2 > 0.75:
            from app.ml.utils import DEMAND_FEATURES, DEMAND_TARGET
            feat_cols = [f for f in DEMAND_FEATURES if f in df_eng.columns]
            target_s  = df_eng[DEMAND_TARGET].dropna()
            corrs = {
                f: abs(float(df_eng[f].dropna().corr(target_s)))
                for f in feat_cols if f in df_eng.columns
            }
            top5 = sorted(corrs, key=corrs.get, reverse=True)[:5]
            print("  Top-5 features by |corr| with demand target:")
            for feat in top5:
                print(f"    {feat}: {corrs[feat]:.4f}")
            print("  Stopping — fix residual leak before proceeding.")
            sys.exit(1)

print("\nDone.")

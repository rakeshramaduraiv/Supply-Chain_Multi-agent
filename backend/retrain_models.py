from app.ml.training import TrainingOrchestrator
from app.feature_engineering import engineer_features
import pandas as pd, sys

df = pd.read_csv('data/raw/DataCoSupplyChainDataset.csv', encoding='latin-1')
print(f"Loaded {len(df)} rows", flush=True)
df_eng = engineer_features(df)
print(f"Engineered {len(df_eng.columns)} columns", flush=True)
orch = TrainingOrchestrator()
results = orch.train_all(df_eng, dataset_version='feature_rename_v1')
for k, v in results.items():
    print(f"{k}: {v.version_id} metrics={list(v.metrics.items())[:3]}", flush=True)
print("Retrain complete", flush=True)

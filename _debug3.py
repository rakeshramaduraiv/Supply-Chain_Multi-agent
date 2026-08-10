import os, sys
sys.path.insert(0, '/app')
os.chdir('/app')

from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType, FEATURE_CONFIGS
from app.ml.utils import chronological_split
import pandas as pd, numpy as np
from pathlib import Path

r = ModelRegistry()
df = pd.read_parquet('/app/data/uploads/processed_master.parquet')
_, test_df = chronological_split(df, train_ratio=0.8)

for it in [IntelligenceType.DEMAND, IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS]:
    v = r.get_latest_version(it)
    if not v: continue
    fc = FEATURE_CONFIGS[it]
    features = v.features_used or []
    available = [f for f in features if f in test_df.columns and f != fc.target]
    missing = [f for f in features if f not in test_df.columns]
    print(f'{it.value}: features_used={len(features)}, available={len(available)}, missing={missing}')
    if available:
        subset = test_df[available + [fc.target]].dropna()
        print(f'  subset shape: {subset.shape}')
        try:
            model = r.load_model(it)
            X = subset[available]
            y = subset[fc.target]
            pred = model.predict(X)
            print(f'  predict OK: {pred[:3]}')
        except Exception as e:
            print(f'  predict ERROR: {e}')

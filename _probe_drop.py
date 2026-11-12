import pandas as pd, sys
sys.path.insert(0, '/app')
df = pd.read_parquet('/app/data/uploads/processed_master.parquet')
from app.ml.utils import FEATURE_CONFIGS, IntelligenceType

fc = FEATURE_CONFIGS[IntelligenceType.DEMAND]
avail = [f for f in fc.features if f in df.columns and f != fc.target]
subset = df[avail + [fc.target]]
null_mask = subset.isnull().any(axis=1)
dropped = subset[null_mask]
print("Total dropped:", len(dropped))
print("Null counts per col in dropped rows:")
print(dropped.isnull().sum()[dropped.isnull().sum()>0])

# Check which specific features have nulls
for c in avail + [fc.target]:
    n = df[c].isna().sum()
    if n > 0:
        print(f"  {c}: {n} nulls")

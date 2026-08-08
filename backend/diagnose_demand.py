"""Diagnose demand R² after A6 fix."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import logging; logging.basicConfig(level=logging.WARNING)
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import r2_score
from app.ml.utils import DEMAND_FEATURES, chronological_split
from app.feature_engineering import engineer_features

RAW_CSV = pathlib.Path("data/raw/DataCoSupplyChainDataset.csv")
df_raw = pd.read_csv(RAW_CSV, encoding="latin-1")
train_raw, test_raw = chronological_split(df_raw, 0.8)

from app.feature_engineering import engineer_features, engineer_features_on_test
train_df = engineer_features(train_raw)
test_df  = engineer_features_on_test(test_raw, train_raw)

target = "Order Item Quantity"
avail_train = [f for f in DEMAND_FEATURES if f in train_df.columns]
avail_test  = [f for f in DEMAND_FEATURES if f in test_df.columns]

X_train = train_df[avail_train].fillna(0)
y_train = train_df[target]
X_test  = test_df[avail_test].fillna(0)
y_test  = test_df[target]

print(f"Target distribution (test): mean={y_test.mean():.2f}, std={y_test.std():.2f}")
print(f"  value_counts: {dict(y_test.value_counts().head(8))}")
print()

# Depth-3 tree to check for tautology
tree = DecisionTreeRegressor(max_depth=3, random_state=42)
tree.fit(X_train, y_train)
r2_tree = r2_score(y_test, tree.predict(X_test))
print(f"Depth-3 tree test R2: {r2_tree:.4f}")
imp = sorted(zip(avail_train, tree.feature_importances_), key=lambda x: x[1], reverse=True)
print(f"Top features: {[(f, round(v,4)) for f,v in imp[:6]]}")
print()

# Per-feature correlation with target
print("Feature correlations with target (test set):")
rows = []
for col in avail_test:
    if col in X_test.columns:
        corr = float(np.corrcoef(X_test[col].fillna(0).values, y_test.values)[0,1])
        rows.append((col, round(abs(corr), 4)))
rows.sort(key=lambda x: x[1], reverse=True)
for col, c in rows[:10]:
    flag = " <-- SUSPECT" if c > 0.7 else ""
    print(f"  {col:<40} {c:.4f}{flag}")

# Baseline: predict mean
baseline_r2 = r2_score(y_test, np.full(len(y_test), y_train.mean()))
print(f"\nBaseline (predict mean) R2: {baseline_r2:.4f}")
print(f"Note: for integer targets in 1-5, R2=0.73 may be genuine if lags are informative")
print(f"Key check: are qty_roll_7 / qty_roll_30 correlated with target?")
for col in ["qty_roll_7", "qty_roll_30", "qty_lag_1"]:
    if col in X_test.columns:
        corr = float(np.corrcoef(X_test[col].fillna(0).values, y_test.values)[0,1])
        print(f"  {col}: corr={corr:.4f}")

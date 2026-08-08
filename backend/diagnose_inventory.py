"""Diagnose inventory tautology — find which features reconstruct stockout_risk_flag."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import logging; logging.basicConfig(level=logging.WARNING)

import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import roc_auc_score
from app.ml.utils import INVENTORY_FEATURES, build_stockout_target
from app.feature_engineering import engineer_features

PARQUET = pathlib.Path("data/uploads/processed_master.parquet")
df_raw = pd.read_parquet(PARQUET)

# Engineer on a sample to keep it fast
from app.ml.utils import chronological_split
train_raw, _ = chronological_split(df_raw, 0.8)
df = engineer_features(train_raw)

# Build target
df["stockout_risk_flag"] = build_stockout_target(df)
y = df["stockout_risk_flag"]

avail = [f for f in INVENTORY_FEATURES if f in df.columns]
X = df[avail].fillna(0)

print(f"Features: {avail}")
print(f"Target rate: {y.mean():.3f}")
print()

# Per-feature AUC with depth-1 tree
rows = []
for col in avail:
    tree = DecisionTreeClassifier(max_depth=1, random_state=42)
    tree.fit(X[[col]], y)
    auc = roc_auc_score(y, tree.predict_proba(X[[col]])[:, 1])
    corr = float(np.corrcoef(X[col].values, y.values)[0,1])
    rows.append((col, round(auc,4), round(abs(corr),4)))

rows.sort(key=lambda r: r[1], reverse=True)
print(f"{'Feature':<40} {'AUC-d1':>8} {'|corr|':>8}")
print("-"*58)
for col, auc, corr in rows:
    flag = " <-- SUSPECT" if auc > 0.70 else ""
    print(f"{col:<40} {auc:>8.4f} {corr:>8.4f}{flag}")

# Full depth-3 tree
tree3 = DecisionTreeClassifier(max_depth=3, random_state=42)
tree3.fit(X, y)
auc3 = roc_auc_score(y, tree3.predict_proba(X)[:, 1])
print(f"\nDepth-3 full AUC: {auc3:.4f}")
imp = sorted(zip(avail, tree3.feature_importances_), key=lambda x: x[1], reverse=True)
print("Top importances:", [(f, round(v,4)) for f,v in imp[:6]])

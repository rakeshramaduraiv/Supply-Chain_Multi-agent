"""Test inventory AUC with only non-suspect features."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import logging; logging.basicConfig(level=logging.WARNING)

import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from app.ml.utils import build_stockout_target, chronological_split
from app.feature_engineering import engineer_features

PARQUET = pathlib.Path("data/uploads/processed_master.parquet")
df_raw = pd.read_parquet(PARQUET)
train_raw, _ = chronological_split(df_raw, 0.8)
df = engineer_features(train_raw)
df["stockout_risk_flag"] = build_stockout_target(df)
y = df["stockout_risk_flag"]

# Only features with depth-1 AUC < 0.70 (non-suspect)
safe_features = [
    "supplier_reliability_score", "supplier_hist_late_rate",
    "order_month", "order_quarter", "is_holiday_period",
    "graph_supplier_reliability", "graph_avg_shipping_delay",
    "graph_has_upcoming_event",
]
avail = [f for f in safe_features if f in df.columns]
X = df[avail].fillna(0)

tree3 = DecisionTreeClassifier(max_depth=3, random_state=42)
tree3.fit(X, y)
auc3 = roc_auc_score(y, tree3.predict_proba(X)[:, 1])
print(f"Safe-only depth-3 AUC: {auc3:.4f}")

# Also test with a real model
from lightgbm import LGBMClassifier
lgbm = LGBMClassifier(n_estimators=100, max_depth=5, random_state=42, verbose=-1)
lgbm.fit(X, y)
auc_lgbm = roc_auc_score(y, lgbm.predict_proba(X)[:, 1])
print(f"Safe-only LightGBM train AUC: {auc_lgbm:.4f}")

# Cross-val AUC
from sklearn.model_selection import cross_val_score
cv_auc = cross_val_score(
    LGBMClassifier(n_estimators=100, max_depth=5, random_state=42, verbose=-1),
    X, y, cv=5, scoring="roc_auc"
)
print(f"Safe-only 5-fold CV AUC: {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")
print(f"Target rate: {y.mean():.4f} (very imbalanced — AUC near 0.5 = no signal)")
print()
if cv_auc.mean() < 0.55:
    print("DECISION: DROP Inventory agent — no learnable signal in safe features.")
    print("Write in paper: 'The synthetic stockout target is algebraically derived")
    print("from rolling demand features; no independent inventory signal exists in")
    print("DataCo. The Inventory agent is excluded from Phase 1 evaluation.'")
else:
    print(f"DECISION: KEEP — CV AUC {cv_auc.mean():.4f} in viable range.")
    print(f"Safe features: {avail}")

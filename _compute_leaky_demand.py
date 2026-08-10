"""
Compute leaky demand R² by training a quick LightGBM with the banned features
included, then update data/metrics_history.json with the real before value.
Run inside the container: python3 /app/_compute_leaky_demand.py
"""
import os, sys, json
sys.path.insert(0, '/app')
os.chdir('/app')

import numpy as np
import pandas as pd
from pathlib import Path
from lightgbm import LGBMRegressor
from sklearn.metrics import r2_score

df = pd.read_parquet('/app/data/uploads/processed_master.parquet')

# Leaky demand features (what was used before the ban)
LEAKY_DEMAND_FEATURES = [
    # Banned algebraic transforms of target
    "demand_intensity", "quantity_zscore",
    "revenue_per_unit", "order_value_log",
    "Sales", "Order Item Total", "Order Profit Per Order",
    "category_demand_rank", "discount_rate", "price_ratio",
    # Plus some legitimate ones that were also present
    "order_month", "order_quarter", "order_dayofweek",
]
TARGET = "Order Item Quantity"

available = [f for f in LEAKY_DEMAND_FEATURES if f in df.columns and f != TARGET]
print(f"Available leaky features: {available}")

subset = df[available + [TARGET]].dropna()
split = int(len(subset) * 0.8)
train, test = subset.iloc[:split], subset.iloc[split:]

X_train, y_train = train[available], train[TARGET]
X_test,  y_test  = test[available],  test[TARGET]

model = LGBMRegressor(n_estimators=200, learning_rate=0.1, max_depth=6,
                      random_state=42, n_jobs=-1, verbose=-1)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
r2 = float(r2_score(y_test, y_pred))
print(f"Leaky demand R²: {r2:.4f}")

# Update metrics_history.json
p = Path('/app/data/metrics_history.json')
history = json.loads(p.read_text())
for row in history:
    if row['agent'] == 'Demand':
        row['before'] = round(r2, 4)
        row['note'] = f"before={r2:.4f} computed with leaky features: {available[:5]}..."
        break

p.write_text(json.dumps(history, indent=2))
print("Updated metrics_history.json")
print(json.dumps(history, indent=2))

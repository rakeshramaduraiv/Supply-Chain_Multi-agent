import pandas as pd, numpy as np, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.feature_engineering import engineer_features, ENGINEERED_FEATURES

n = 60
df = pd.DataFrame({
    "order date (DateOrders)": pd.date_range("2016-01-01", periods=n, freq="D"),
    "Department Name":  ["Dept_A", "Dept_B"] * (n // 2),
    "Shipping Mode":    ["Standard Class", "First Class"] * (n // 2),
    "Category Name":    ["Electronics", "Clothing"] * (n // 2),
    "Order Region":     ["West", "East"] * (n // 2),
    "Order Item Quantity": list(range(1, n + 1)),
    "Days for shipping (real)":      [3.0, 4.0, 2.0, 5.0, 3.0, 4.0] * (n // 6),
    "Days for shipment (scheduled)": [2.0, 2.0, 3.0, 3.0, 2.0, 4.0] * (n // 6),
    "Late_delivery_risk": [0, 1] * (n // 2),
    "Sales": [100.0] * n,
    "Order Profit Per Order": [20.0] * n,
    "Order Item Discount": [5.0] * n,
    "Product Price": [50.0] * n,
    "Order Id": list(range(1, n + 1)),
    "Customer Id": list(range(101, 101 + n)),
    "Customer Segment": ["Consumer"] * n,
    "Order City": ["LA", "NY"] * (n // 2),
})

eng = engineer_features(df)

results = []

# Spec-named features
required = [
    "order_year", "order_month", "order_dayofweek", "order_quarter",
    "is_weekend", "is_holiday_period",
    "qty_roll_7", "qty_roll_30", "qty_lag_1", "qty_lag_7", "qty_lag_30",
    "price_ratio", "discount_rate",
    "inventory_stress_index", "days_until_reorder", "reorder_point", "demand_variability",
    "supplier_reliability_score", "supplier_order_volume", "supplier_category_diversity",
    "shipping_mode_encoded", "route_frequency", "region_congestion_index",
    "delivery_gap", "is_delayed", "delivery_duration_days", "shipping_delay_ratio",
    "graph_supplier_reliability", "graph_inventory_stress",
    "graph_avg_shipping_delay", "graph_has_upcoming_event",
]
missing = [f for f in required if f not in eng.columns]
results.append(f"Missing spec features: {missing if missing else 'NONE'}")

# Graph context columns must be non-constant
for col in ["graph_supplier_reliability", "graph_inventory_stress", "graph_avg_shipping_delay"]:
    nu = eng[col].nunique()
    sd = eng[col].std()
    status = "OK" if nu > 1 and sd > 0 else "FAIL-CONSTANT"
    results.append(f"{col}: nunique={nu} std={sd:.4f} [{status}]")

# days_until_reorder must not be all-zero
dur_min = eng["days_until_reorder"].min()
dur_max = eng["days_until_reorder"].max()
dur_status = "OK" if dur_max > 0 else "FAIL-ALL-ZERO"
results.append(f"days_until_reorder: min={dur_min:.2f} max={dur_max:.2f} [{dur_status}]")

# graph_has_upcoming_event must be binary
ghe_vals = sorted(eng["graph_has_upcoming_event"].unique().tolist())
results.append(f"graph_has_upcoming_event values: {ghe_vals}")

with open("feature_eng_results.txt", "w") as f:
    f.write("\n".join(results) + "\n")
    f.write("feature_engineering DONE\n")

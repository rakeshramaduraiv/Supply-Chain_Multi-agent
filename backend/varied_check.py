import pandas as pd, numpy as np, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from app.feature_engineering import engineer_features

n = 60
rng = np.random.default_rng(42)
df = pd.DataFrame({
    "order date (DateOrders)": pd.date_range("2016-01-01", periods=n, freq="D"),
    "Department Name":  ["Dept_A", "Dept_B"] * (n // 2),
    "Shipping Mode":    ["Standard Class", "First Class"] * (n // 2),
    "Category Name":    ["Electronics", "Clothing"] * (n // 2),
    "Order Region":     ["West", "East"] * (n // 2),
    "Order Item Quantity": rng.integers(1, 20, n),
    "Days for shipping (real)":      rng.integers(2, 8, n).astype(float),
    "Days for shipment (scheduled)": rng.integers(2, 5, n).astype(float),
    "Late_delivery_risk": rng.integers(0, 2, n),
    "Sales": rng.uniform(50, 500, n),
    "Order Profit Per Order": rng.uniform(5, 50, n),
    "Order Item Discount": rng.uniform(0, 20, n),
    "Product Price": rng.uniform(20, 200, n),
    "Order Id": list(range(1, n + 1)),
    "Customer Id": list(range(101, 101 + n)),
    "Customer Segment": ["Consumer"] * n,
    "Order City": ["LA", "NY"] * (n // 2),
})
eng = engineer_features(df)
lines = []
for col in ["graph_supplier_reliability", "graph_inventory_stress", "graph_avg_shipping_delay"]:
    nu = eng[col].nunique()
    sd = eng[col].std()
    status = "OK" if nu > 1 and sd > 0 else "FAIL-CONSTANT"
    lines.append(f"{col}: nunique={nu} std={sd:.4f} [{status}]")
lines.append(f"days_until_reorder: min={eng['days_until_reorder'].min():.2f} max={eng['days_until_reorder'].max():.2f}")
lines.append("varied data check DONE")
with open("varied_results.txt", "w") as f:
    f.write("\n".join(lines) + "\n")

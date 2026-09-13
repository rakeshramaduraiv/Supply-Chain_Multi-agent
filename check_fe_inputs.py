import sys
sys.path.insert(0, "/app")
import pandas as pd

pre = pd.read_csv("data/stages/2_preprocessed_full.csv", nrows=0)
print("PREPROCESSED COLUMNS:", list(pre.columns))

# These are the 13 raw columns that feed feature engineering
FE_INPUT_COLS = [
    "order date (DateOrders)",
    "Order Item Quantity",
    "Product Price",
    "Order Item Discount",
    "Sales",
    "Days for shipment (scheduled)",
    "Days for shipping (real)",
    "Department Name",
    "Shipping Mode",
    "Order Region",
    "Category Name",
    "Late_delivery_risk",
    "Order Country",
]

present = [c for c in FE_INPUT_COLS if c in pre.columns]
missing = [c for c in FE_INPUT_COLS if c not in pre.columns]
print("\nFE INPUT COLS present:", present)
print("FE INPUT COLS missing:", missing)

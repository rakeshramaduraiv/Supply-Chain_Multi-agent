import pandas as pd, numpy as np, sys, json
sys.path.insert(0, '/app')

raw = pd.read_csv('/app/data/raw/DataCoSupplyChainDataset.csv', encoding='latin-1')
df  = pd.read_parquet('/app/data/uploads/processed_master.parquet')

print("=== RAW SHAPE ===")
print(raw.shape)

print("\n=== DQ CHECKS ===")
print("Product Description nulls:", raw['Product Description'].isna().sum())
print("Order Zipcode nulls:", raw['Order Zipcode'].isna().sum() if 'Order Zipcode' in raw.columns else 'N/A')
print("Customer Lname nulls:", raw['Customer Lname'].isna().sum() if 'Customer Lname' in raw.columns else 'N/A')
print("Customer Zipcode nulls:", raw['Customer Zipcode'].isna().sum() if 'Customer Zipcode' in raw.columns else 'N/A')
print("Negative profit rows:", (raw['Order Profit Per Order'] < 0).sum())
print("Negative benefit rows:", (raw['Benefit per order'] < 0).sum() if 'Benefit per order' in raw.columns else 'N/A')
print("Benefit per order min:", raw['Benefit per order'].min() if 'Benefit per order' in raw.columns else 'N/A')
print("Duplicate rows:", raw.duplicated().sum())
ldr = raw['Late_delivery_risk'].value_counts()
print("Late_delivery_risk:", ldr.to_dict())
print("Order Item Id unique:", raw['Order Item Id'].nunique() if 'Order Item Id' in raw.columns else 'N/A')
for c in ['Customer Email','Customer Password','Product Status']:
    if c in raw.columns:
        print(f'{c} nunique:', raw[c].nunique())

# Date range
date_col = 'order date (DateOrders)'
if date_col in raw.columns:
    dates = pd.to_datetime(raw[date_col], errors='coerce')
    print("Date min:", dates.min(), "max:", dates.max())
    print("Unparseable dates:", dates.isna().sum())

# Shipping < order
ship_col = 'shipping date (DateOrders)'
if date_col in raw.columns and ship_col in raw.columns:
    od = pd.to_datetime(raw[date_col], errors='coerce')
    sd = pd.to_datetime(raw[ship_col], errors='coerce')
    bad = ((sd < od) & sd.notna() & od.notna()).sum()
    print("Shipping before order:", bad)

# Geographic / product scope
for c in ['Order Country','Order Region','Department Name','Category Name']:
    if c in raw.columns:
        print(f"{c} nunique:", raw[c].nunique())

print("\n=== ROW ACCOUNTING ===")
from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
for name, intel in [('demand', IntelligenceType.DEMAND), ('supplier', IntelligenceType.SUPPLIER), ('logistics', IntelligenceType.LOGISTICS)]:
    fc = FEATURE_CONFIGS[intel]
    avail = [f for f in fc.features if f in df.columns and f != fc.target]
    # target dropna first
    df_t = df.dropna(subset=[fc.target])
    # then feature dropna
    df_f = df_t[avail + [fc.target]].dropna()
    split = int(len(df)*0.8)
    train_sub = df_f.iloc[:split]
    test_sub  = df_f.iloc[split:]
    print(f"{name}: rows_in={len(df)}, after_target_dropna={len(df_t)}, after_feature_dropna={len(df_f)}, train={len(train_sub)}, test={len(test_sub)}, dropped={len(df)-len(df_f)}")

print("\n=== LEAKY CORRELATIONS ===")
leaky_cols = ['is_delayed','delivery_gap','delivery_duration_days','shipping_delay_ratio','composite_risk_score','revenue_per_unit','supplier_delay_rate']
target = 'Late_delivery_risk'
for c in leaky_cols:
    if c in df.columns and target in df.columns:
        corr = abs(df[c].corr(df[target]))
        print(f"{c}: |pearson|={corr:.4f}")

print("\n=== GRAPH DELTA (tier1 vs tier2) ===")
gcols = ['graph_supplier_reliability','graph_inventory_stress','graph_avg_shipping_delay','graph_tpke_edge_density']
t1 = pd.read_parquet('/app/data/stages/3_tier1_features_full.parquet')
t2 = df
for c in gcols:
    if c in t1.columns and c in t2.columns:
        v1 = pd.to_numeric(t1[c], errors='coerce').fillna(0)
        v2 = pd.to_numeric(t2[c], errors='coerce').fillna(0)
        diff = (v2 - v1).abs()
        corr = float(v1.corr(v2)) if v1.std()>0 and v2.std()>0 else 1.0
        r2 = corr**2
        print(f"{c}: mean_abs_delta={diff.mean():.6f}, median_abs_delta={diff.median():.6f}, max={diff.max():.6f}, std={diff.std():.6f}, pearson={corr:.6f}, pct_var_unexplained={1-r2:.6f}, pct_rows_changed={((diff>1e-9).sum()/len(diff)*100):.2f}%")

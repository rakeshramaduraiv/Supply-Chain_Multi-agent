import psycopg2, os, sys
sys.path.insert(0, '/app')
os.chdir('/app')

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST','postgres'), port=int(os.getenv('POSTGRES_PORT',5432)),
    user=os.getenv('POSTGRES_USER','amasci_user'), password=os.getenv('POSTGRES_PASSWORD','amasci_dev_pass'),
    dbname=os.getenv('POSTGRES_DB','amasci_db'),
)
cur = conn.cursor()
cur.execute("SELECT name, model_type, version, accuracy, rmse, mae, f1_score, training_rows, created_at FROM trained_models ORDER BY created_at")
print('trained_models:', cur.fetchall())
conn.close()

# Registry (file-based)
from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType
r = ModelRegistry()
for it in [IntelligenceType.DEMAND, IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS]:
    v = r.get_latest_version(it)
    if v:
        print(f'\n{it.value}: metrics={v.metrics}, n_samples={v.n_training_samples}, features={len(v.features_used or [])}')
        print(f'  hyperparams keys: {list((v.hyperparameters or {}).keys())}')

# Parquet
import pandas as pd
df = pd.read_parquet('/app/data/uploads/processed_master.parquet')
print('\nShape:', df.shape)
print('Cols:', list(df.columns))
print('Date range:', df['order date (DateOrders)'].min(), '->', df['order date (DateOrders)'].max())
print('Markets:', df['Market'].value_counts().to_dict())
print('Shipping modes:', df['Shipping Mode'].value_counts().to_dict())
print('Late delivery rate:', round(df['Late_delivery_risk'].mean(), 4))
print('Top categories:', df['Category Name'].value_counts().head(5).to_dict())
print('Order status:', df['Order Status'].value_counts().to_dict() if 'Order Status' in df.columns else 'N/A')
print('Dept:', df['Department Name'].value_counts().head(5).to_dict() if 'Department Name' in df.columns else 'N/A')

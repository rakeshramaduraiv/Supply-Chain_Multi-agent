import sys, logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
sys.path.insert(0, "/app")
import pandas as pd
from app.data_engineering.pipeline import DataEngineeringPipeline

df_raw = pd.read_csv("data/raw/DataCoSupplyChainDataset.csv", encoding="latin-1")
print(f"Raw: {df_raw.shape}")

pipeline = DataEngineeringPipeline()
df_processed, result = pipeline.execute(df_raw, dataset_id="check")
print(f"Processed: {df_processed.shape}")

id_cols = [c for c in df_processed.columns if any(k in c.lower() for k in ['id', 'cardprod'])]
print(f"ID cols remaining: {id_cols}")

df_processed.to_csv("data/stages/2_preprocessed_full.csv", index=False)
print("Written: data/stages/2_preprocessed_full.csv")
print("Columns:", list(df_processed.columns))

import pandas as pd

raw = pd.read_csv('data/raw/DataCoSupplyChainDataset.csv', encoding='latin-1', nrows=0)
pre = pd.read_csv('data/stages/2_preprocessed_full.csv', nrows=0)

raw_cols = list(raw.columns)
pre_cols = list(pre.columns)
raw_set  = set(raw_cols)
pre_set  = set(pre_cols)

print(f"RAW: {len(raw_cols)} columns")
print(f"PREPROCESSED: {len(pre_cols)} columns")

print("\n--- DROPPED (raw -> removed during cleaning) ---")
for c in raw_cols:
    if c not in pre_set:
        print(f"  DROPPED: {c}")

print("\n--- ADDED (new columns created during transformation) ---")
for c in pre_cols:
    if c not in raw_set:
        print(f"  ADDED: {c}")

print("\n--- KEPT (unchanged from raw) ---")
kept = [c for c in raw_cols if c in pre_set]
print(f"  {len(kept)} columns kept")
for c in kept:
    print(f"  KEPT: {c}")

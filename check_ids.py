import pandas as pd

pre = pd.read_csv('data/stages/2_preprocessed_full.csv', nrows=5)

id_keywords = ['id', 'zipcode', 'card', 'image']
id_cols = []
non_id_cols = []

for c in pre.columns:
    if any(k in c.lower() for k in id_keywords):
        id_cols.append(c)
    else:
        non_id_cols.append(c)

print(f"TOTAL COLUMNS: {len(pre.columns)}")
print(f"\nID / IDENTIFIER COLUMNS ({len(id_cols)}) — not features:")
for c in id_cols:
    print(f"  {c}  sample={pre[c].iloc[0]}")

print(f"\nNON-ID COLUMNS ({len(non_id_cols)}) — actual data:")
for c in non_id_cols:
    print(f"  {c}")

# User Upload Files — DataCo Holdout Months

These 4 CSV files are the **last 4 months** cut from the original DataCo Supply Chain dataset.
The models were trained on everything BEFORE October 2017.
These files are the real unseen data — upload them one by one to evaluate model performance.

## Files

| File | Period | Rows | Upload Order |
|------|--------|------|--------------|
| UPLOAD_1_October_2017.csv  | 2017-10 | 2,255 | Upload first  |
| UPLOAD_2_November_2017.csv | 2017-11 | 2,055 | Upload second |
| UPLOAD_3_December_2017.csv | 2017-12 | 2,124 | Upload third  |
| UPLOAD_4_January_2018.csv  | 2018-01 | 2,123 | Upload fourth |

## How to Upload

1. Start the app: `docker compose -f docker-compose.dev.yml up -d` then `cd frontend && npm run dev`
2. Open http://localhost:5173
3. Click **"Upload Actuals"** in the top navigation
4. Upload files **in order** (1 → 2 → 3 → 4)
5. Watch the dashboard update in real time after each upload

## What Happens After Upload

- The backend runs the ML models on the uploaded data
- Supplier AUC, Logistics AUC, Demand MAE, R² are computed against real outcomes
- The Knowledge Graph (TPKE) evolves based on the new data
- All dashboard KPIs update immediately to reflect the uploaded actuals

## Note on Cycle 1

October 2017 (Cycle 1) has no prior forecast to compare against — stages 2 and 3
are skipped for that month. Real metrics begin from November 2017 (Cycle 2).

## Source

These files were split from:
  `backend/data/raw/DataCoSupplyChainDataset.csv`

The training set (171,962 rows, Jan 2015 – Sep 2017) is at:
  `backend/data/raw/DataCoSupplyChainDataset_train.csv`

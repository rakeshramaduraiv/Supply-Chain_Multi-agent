# data/actuals/ — SYNTHETIC FILES — DO NOT USE AS HOLDOUT ACTUALS

These CSV files are **synthetic** and are NOT the real holdout actuals.

## Real holdout actuals are in `data/actuals_real/`

| File | Period | Rows | Source |
|------|--------|------|--------|
| `2017_10_actual.csv` | 2017-10 | 2,255 | Real DataCo holdout |
| `2017_11_actual.csv` | 2017-11 | 2,055 | Real DataCo holdout |
| `2017_12_actual.csv` | 2017-12 | 2,124 | Real DataCo holdout |
| `2018_01_actual.csv` | 2018-01 | 2,123 | Real DataCo holdout |

## What this directory contains

Synthetic files generated for demo/testing purposes only.
They do NOT represent real DataCo orders and must never be used to evaluate
model accuracy or as inputs to the forecast lifecycle.

## System configuration

`ACTUALS_DIR=data/actuals_real` in `.env` ensures the cycle always reads
from the real holdout directory.  `resolve_actuals_dir()` in
`app/core/data_files.py` enforces this.

## Data leakage boundary

Training data: 2015-01-01 to 2017-09-30 (171,962 rows)
Holdout start: 2017-10-01 (`HOLDOUT_START_DATE` in `.env`)

The initialization service hard-filters all rows on or after 2017-10-01
before training.  `assert_parquet_integrity()` raises if any holdout date
appears in the training parquet.

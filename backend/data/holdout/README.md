# Holdout Data — Real Withheld Months

These four CSV files are **genuine DataCo orders that were withheld from all
model training**. They are not synthetic. They are not augmented. They are the
original rows from the source dataset, untouched.

## What is here

| File | Month | Rows |
|---|---|---|
| `2017_10.csv` | October 2017 | 2,255 |
| `2017_11.csv` | November 2017 | 2,055 |
| `2017_12.csv` | December 2017 | 2,124 |
| `2018_01.csv` | January 2018 | 2,123 |
| **Total** | | **8,557** |

## Training cutoff

**2017-09-30 23:59:59**

All rows with `order date (DateOrders)` on or before this date were used for
training (171,961 rows). All rows after this date are in this folder and were
never seen by any model during initialization.

## Why this matters

A holdout that the model has already trained on is worthless. The cutoff is
enforced structurally in `initialization/service.py` via a
`HoldoutContaminationError` guard that runs immediately after load and again
immediately before training. The guard raises loudly if any date in the loaded
frame exceeds the cutoff — there is no silent fallback.

## Volume drop note

Monthly order volume drops from ~5,200 to ~2,200 at October 2017. This is
real, present in the source data, and coincides with the holdout boundary.
It is not a data error and has not been corrected.

## Schema

All four files contain all 53 original DataCo columns, unmodified. They pass
the existing upload validation unchanged (raw schema, same column set as the
training data).

## Intended use

Upload one file per month through the UI Data page → "Load holdout month"
panel. Each upload triggers a full closed-loop evaluation cycle on genuinely
unseen real data.

After all four real months are consumed, the `data/monthly_synthetic_uploads/`
files provide synthetic continuation for demonstrating cycles 5+. See that
folder's README for details. The distinction is important for the paper:
**four real evaluation cycles, then synthetic continuation**.

## Regenerating

```bash
python scripts/build_holdout.py --months 4
```

The script is idempotent and safe to re-run. Use `--dry-run` to verify the
plan without writing anything.

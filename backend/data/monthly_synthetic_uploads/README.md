# Legacy Data — Synthetic Continuation

> **Status: LEGACY** — superseded by `data/holdout/` for the first four evaluation cycles.

## What is here

`monthly_synthetic_uploads/` and `continuation/` contain synthetically generated
monthly CSV files that mimic DataCo order patterns. They were used during
development to simulate closed-loop cycles before the real holdout split was
implemented.

## When to use these

These files are **not real data**. Use them only after the four real holdout
months (`data/holdout/2017_10.csv` through `2018_01.csv`) have been consumed.

The intended sequence for the paper is:

1. **Cycles 1–4**: Upload the four real holdout months in order.
   These are genuine DataCo orders the model has never seen.
2. **Cycles 5+**: Upload synthetic months from this folder to demonstrate
   continued closed-loop operation beyond the real data window.

This distinction must survive into the paper:
**four real evaluation cycles, then synthetic continuation**.

## Why they still exist

Deleting them would break any demo that has already consumed the four real
months. They remain useful for showing the system operating beyond the real
data window.

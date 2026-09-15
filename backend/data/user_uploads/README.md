# user_uploads/

This directory is the destination for CSV files uploaded at runtime via the
`POST /api/v1/business/upload/actual` endpoint.

## Holdout evaluation files

The four real held-out months (Oct 2017 – Jan 2018) are **not** stored here.
They live in their canonical location:

    backend/data/actuals_real/
        2017_10_actual.csv   (2,255 rows)
        2017_11_actual.csv   (2,055 rows)
        2017_12_actual.csv   (2,124 rows)
        2018_01_actual.csv   (2,123 rows)

The `GET /api/v1/business/holdout-file/{filename}` endpoint serves files
directly from `actuals_real/`. There is no duplication.

## Regenerating the holdout files

If `actuals_real/` is empty, run:

    cd backend
    python -m scripts.create_holdout_actuals

This requires `backend/data/raw/DataCoSupplyChainDataset.csv` to be present.
See the "Reproducing from a clean clone" section in the root README.

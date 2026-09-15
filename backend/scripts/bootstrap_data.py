"""
scripts/bootstrap_data.py
==========================
Verify the raw DataCo CSV is present and correctly shaped, then regenerate
the training split and the four holdout actuals.

Run from the backend/ directory:
    python -m scripts.bootstrap_data

Exit codes:
    0  — success
    1  — raw CSV missing or wrong shape
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).parent.parent
RAW_CSV = BACKEND / "data" / "raw" / "DataCoSupplyChainDataset.csv"

EXPECTED_ROWS = 180_519
EXPECTED_COLS = 53
EXPECTED_DATE_MIN = "2015-01-01"
EXPECTED_DATE_MAX = "2018-01-31"
DATE_COL = "order date (DateOrders)"

MENDELEY_DOI = "10.17632/8gx2fvg2k6.5"
KAGGLE_URL   = "https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis"


def _check_csv() -> bool:
    if not RAW_CSV.exists():
        print("=" * 60)
        print("ERROR: Raw dataset not found.")
        print(f"  Expected: {RAW_CSV}")
        print()
        print("Download the DataCo Smart Supply Chain dataset and place it at:")
        print(f"  {RAW_CSV}")
        print()
        print("Sources:")
        print(f"  Mendeley Data  : https://doi.org/{MENDELEY_DOI}")
        print(f"  Kaggle mirror  : {KAGGLE_URL}")
        print()
        print("Expected file properties:")
        print(f"  Filename : DataCoSupplyChainDataset.csv")
        print(f"  Rows     : {EXPECTED_ROWS:,}")
        print(f"  Columns  : {EXPECTED_COLS}")
        print(f"  Encoding : latin-1")
        print("=" * 60)
        return False
    return True


def _verify_shape() -> bool:
    import pandas as pd

    print(f"Loading {RAW_CSV.name} …")
    df = pd.read_csv(RAW_CSV, encoding="latin-1")
    rows, cols = df.shape
    print(f"  Shape: {rows:,} rows × {cols} columns")

    ok = True
    if rows != EXPECTED_ROWS:
        print(f"  WARNING: expected {EXPECTED_ROWS:,} rows, got {rows:,}")
        ok = False
    if cols != EXPECTED_COLS:
        print(f"  WARNING: expected {EXPECTED_COLS} columns, got {cols}")
        ok = False

    if DATE_COL in df.columns:
        dates = pd.to_datetime(df[DATE_COL], errors="coerce").dropna()
        actual_min = str(dates.min().date())
        actual_max = str(dates.max().date())
        print(f"  Date range: {actual_min} to {actual_max}")
        if actual_min > EXPECTED_DATE_MIN:
            print(f"  WARNING: expected date min <= {EXPECTED_DATE_MIN}, got {actual_min}")
            ok = False
        if actual_max < EXPECTED_DATE_MAX:
            print(f"  WARNING: expected date max >= {EXPECTED_DATE_MAX}, got {actual_max}")
            ok = False
    else:
        print(f"  WARNING: date column '{DATE_COL}' not found")
        ok = False

    return ok


def _run_split() -> None:
    from scripts.create_holdout_actuals import run
    print()
    print("Running create_holdout_actuals …")
    run(holdout_start="2017-10-01", months=4, dry_run=False)


def _print_summary() -> None:
    import pandas as pd

    actuals_dir = BACKEND / "data" / "actuals_real"
    train_csv   = BACKEND / "data" / "raw" / "DataCoSupplyChainDataset_train.csv"

    print()
    print("=" * 60)
    print("Bootstrap verification table")
    print("=" * 60)

    if train_csv.exists():
        df_train = pd.read_csv(train_csv, usecols=[DATE_COL])
        dates = pd.to_datetime(df_train[DATE_COL], errors="coerce").dropna()
        print(f"  Training rows : {len(df_train):,}")
        print(f"  Training max  : {dates.max().date()}")
    else:
        print("  Training CSV  : NOT FOUND")

    holdout_files = [
        ("2017-10", "2017_10_actual.csv"),
        ("2017-11", "2017_11_actual.csv"),
        ("2017-12", "2017_12_actual.csv"),
        ("2018-01", "2018_01_actual.csv"),
    ]
    total_holdout = 0
    for month, fname in holdout_files:
        p = actuals_dir / fname
        if p.exists():
            n = sum(1 for _ in open(p, encoding="utf-8")) - 1  # subtract header
            total_holdout += n
            print(f"  Holdout {month} : {n:,} rows  ({fname})")
        else:
            print(f"  Holdout {month} : MISSING ({fname})")

    print(f"  Total holdout : {total_holdout:,} rows")
    print("=" * 60)
    print("Bootstrap complete. You can now run initialization.")
    print()


def main() -> None:
    if not _check_csv():
        sys.exit(1)

    shape_ok = _verify_shape()
    if not shape_ok:
        print()
        print("Shape/date warnings above. Proceeding with split anyway.")
        print("If row count is wrong, verify you have the correct file.")

    _run_split()
    _print_summary()


if __name__ == "__main__":
    main()

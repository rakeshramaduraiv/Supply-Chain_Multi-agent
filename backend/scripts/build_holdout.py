"""
build_holdout.py
================
Carve a real N-month holdout from DataCoSupplyChainDataset.csv.

Usage:
    python scripts/build_holdout.py --months 4 [--dry-run]

Outputs (when not --dry-run):
    data/raw/DataCoSupplyChainDataset_train.csv      — rows <= cutoff
    data/holdout/2017_10.csv  ...  2018_01.csv       — one file per holdout month
    data/holdout/00_holdout_manifest.csv             — audit manifest
"""

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

# ── paths ─────────────────────────────────────────────────────────────────────
_ROOT      = Path(__file__).resolve().parents[1]          # backend/
_RAW_CSV   = _ROOT / "data" / "raw" / "DataCoSupplyChainDataset.csv"
_TRAIN_CSV = _ROOT / "data" / "raw" / "DataCoSupplyChainDataset_train.csv"
_HOLDOUT   = _ROOT / "data" / "holdout"
_DATE_COL  = "order date (DateOrders)"
_TOTAL_ROWS = 180_519
_EXPECTED_CUTOFF = pd.Timestamp("2017-09-30")


# ── helpers ───────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _derive_cutoff(df: pd.DataFrame, months: int) -> pd.Timestamp:
    """
    Cutoff = last day of the (months+1)th-from-last calendar month.
    E.g. for months=4 and max month 2018-01:
        last 4 months = 2017-10, 2017-11, 2017-12, 2018-01
        cutoff        = last day of 2017-09 = 2017-09-30
    """
    dates = pd.to_datetime(df[_DATE_COL], errors="coerce").dropna()
    all_months = sorted(dates.dt.to_period("M").unique())
    if len(all_months) < months + 1:
        sys.exit(f"ERROR: dataset has only {len(all_months)} months; cannot carve {months}.")
    cutoff_period = all_months[-(months + 1)]
    # last day of that period
    return cutoff_period.to_timestamp("D", how="end").normalize()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build DataCo holdout split")
    parser.add_argument("--months", type=int, default=4,
                        help="Number of trailing months to hold out (default: 4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan and manifest; write nothing")
    args = parser.parse_args()

    if not _RAW_CSV.exists():
        sys.exit(f"ERROR: raw CSV not found at {_RAW_CSV}")

    print(f"Loading {_RAW_CSV.name} …")
    df = pd.read_csv(_RAW_CSV, encoding="latin-1")
    df[_DATE_COL] = pd.to_datetime(df[_DATE_COL], errors="coerce")
    df = df.sort_values(_DATE_COL).reset_index(drop=True)

    cutoff = _derive_cutoff(df, args.months)

    # ── Assert derived cutoff matches expected value for N=4 ──────────────────
    if args.months == 4 and cutoff != _EXPECTED_CUTOFF:
        sys.exit(
            f"ASSERTION FAILED: derived cutoff {cutoff.date()} != "
            f"expected {_EXPECTED_CUTOFF.date()}. "
            f"The input file may have changed. Aborting."
        )

    train_df   = df[df[_DATE_COL] <= cutoff].copy()
    holdout_df = df[df[_DATE_COL] >  cutoff].copy()

    holdout_months = sorted(
        holdout_df[_DATE_COL].dt.to_period("M").unique()
    )

    # ── Pre-write assertions ──────────────────────────────────────────────────
    errors: list[str] = []

    if len(train_df) + len(holdout_df) != _TOTAL_ROWS:
        errors.append(
            f"Row count mismatch: train({len(train_df)}) + holdout({len(holdout_df)}) "
            f"= {len(train_df)+len(holdout_df)} != {_TOTAL_ROWS}"
        )

    train_dates   = set(train_df[_DATE_COL].dropna().dt.date)
    holdout_dates = set(holdout_df[_DATE_COL].dropna().dt.date)
    overlap = train_dates & holdout_dates
    if overlap:
        errors.append(f"Date overlap between train and holdout: {sorted(overlap)[:5]} …")

    if len(holdout_months) != args.months:
        errors.append(
            f"Expected {args.months} holdout months, got {len(holdout_months)}: {holdout_months}"
        )

    for m in holdout_months:
        if len(holdout_df[holdout_df[_DATE_COL].dt.to_period("M") == m]) == 0:
            errors.append(f"Holdout month {m} is empty")

    if set(train_df.columns) != set(holdout_df.columns):
        errors.append("Column sets differ between train and holdout")

    if errors:
        sys.exit("ASSERTION ERRORS — nothing written:\n  " + "\n  ".join(errors))

    # ── Build manifest ────────────────────────────────────────────────────────
    manifest_rows = []
    for m in holdout_months:
        mdf = holdout_df[holdout_df[_DATE_COL].dt.to_period("M") == m]
        fname = f"{m.year}_{m.month:02d}.csv"
        manifest_rows.append({
            "month":         str(m),
            "filename":      fname,
            "rows":          len(mdf),
            "date_min":      str(mdf[_DATE_COL].min().date()),
            "date_max":      str(mdf[_DATE_COL].max().date()),
            "late_rate":     round(float(mdf["Late_delivery_risk"].mean()), 4)
                             if "Late_delivery_risk" in mdf.columns else None,
            "mean_quantity": round(float(mdf["Order Item Quantity"].mean()), 4)
                             if "Order Item Quantity" in mdf.columns else None,
            "n_categories":  int(mdf["Category Name"].nunique())
                             if "Category Name" in mdf.columns else None,
            "n_regions":     int(mdf["Order Region"].nunique())
                             if "Order Region" in mdf.columns else None,
            "sha256":        "(dry-run)" if args.dry_run else None,  # filled below
        })

    # ── Print plan ────────────────────────────────────────────────────────────
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Holdout plan")
    print(f"  Cutoff          : {cutoff.date()}")
    print(f"  Train rows      : {len(train_df):,}")
    print(f"  Holdout rows    : {len(holdout_df):,}")
    print(f"  Holdout months  : {args.months}")
    print()
    print(f"  {'Month':<10} {'Rows':>7}  {'Date min':<12} {'Date max':<12} "
          f"{'Late rate':>10} {'Mean qty':>9} {'Cats':>5} {'Regions':>8}")
    print("  " + "-" * 75)
    for r in manifest_rows:
        print(f"  {r['month']:<10} {r['rows']:>7,}  {r['date_min']:<12} {r['date_max']:<12} "
              f"{str(r['late_rate']):>10} {str(r['mean_quantity']):>9} "
              f"{str(r['n_categories']):>5} {str(r['n_regions']):>8}")

    # ── Volume-drop note ──────────────────────────────────────────────────────
    print()
    print("  NOTE: monthly volume drops from ~5,200 to ~2,200 at 2017-10.")
    print("  This is real, present in the source data, and coincides with")
    print("  the holdout boundary. It is NOT a data error — do not fix it.")

    if args.dry_run:
        print("\nDry run complete — nothing written.")
        return

    # ── Write files ───────────────────────────────────────────────────────────
    _HOLDOUT.mkdir(parents=True, exist_ok=True)

    print(f"\nWriting {_TRAIN_CSV.name} ({len(train_df):,} rows) …")
    train_df.to_csv(_TRAIN_CSV, index=False, encoding="latin-1")

    for r, m in zip(manifest_rows, holdout_months):
        mdf = holdout_df[holdout_df[_DATE_COL].dt.to_period("M") == m]
        out = _HOLDOUT / r["filename"]
        print(f"Writing {out.name} ({len(mdf):,} rows) …")
        mdf.to_csv(out, index=False, encoding="latin-1")
        r["sha256"] = _sha256(out)

    manifest_path = _HOLDOUT / "00_holdout_manifest.csv"
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
    print(f"Writing {manifest_path.name} …")

    print(f"\nDone. Train: {len(train_df):,} rows, Holdout: {len(holdout_df):,} rows.")
    print(f"Verify: {len(train_df) + len(holdout_df):,} == {_TOTAL_ROWS} ✓")


if __name__ == "__main__":
    main()

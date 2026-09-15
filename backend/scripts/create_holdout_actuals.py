"""
scripts/create_holdout_actuals.py
===================================
Split DataCoSupplyChainDataset.csv into a training corpus and four real
held-out months (2017-10 through 2018-01).

Usage:
    python -m scripts.create_holdout_actuals [--holdout-start 2017-10-01] [--months 4] [--dry-run]

Outputs (all in backend/data/actuals_real/):
    DataCoSupplyChainDataset_train.csv   — training corpus (rows < holdout_start)
    2017_10_actual.csv                   — Oct 2017 holdout
    2017_11_actual.csv                   — Nov 2017 holdout
    2017_12_actual.csv                   — Dec 2017 holdout
    2018_01_actual.csv                   — Jan 2018 holdout
    holdout_manifest.csv                 — per-month statistics + training row

The original DataCoSupplyChainDataset.csv is NEVER modified or deleted.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).parent.parent
RAW_CSV = BACKEND / "data" / "raw" / "DataCoSupplyChainDataset.csv"
OUT_DIR = BACKEND / "data" / "actuals_real"
TRAIN_CSV = BACKEND / "data" / "raw" / "DataCoSupplyChainDataset_train.csv"

DATE_COL = "order date (DateOrders)"

EXPECTED_TOTAL = 180_519
EXPECTED_TRAIN = 171_962
EXPECTED_HOLDOUT = 8_557
EXPECTED_MONTHLY = {
    "2017-10": 2255,
    "2017-11": 2055,
    "2017-12": 2124,
    "2018-01": 2123,
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _month_stats(df: pd.DataFrame, label: str) -> dict:
    return {
        "split": label,
        "rows": len(df),
        "date_min": str(pd.to_datetime(df[DATE_COL], errors="coerce").min().date()),
        "date_max": str(pd.to_datetime(df[DATE_COL], errors="coerce").max().date()),
        "late_rate": round(float(df["Late_delivery_risk"].mean()), 6) if "Late_delivery_risk" in df.columns else None,
        "mean_quantity": round(float(df["Order Item Quantity"].mean()), 4) if "Order Item Quantity" in df.columns else None,
        "n_unique_categories": int(df["Category Name"].nunique()) if "Category Name" in df.columns else None,
        "n_unique_regions": int(df["Order Region"].nunique()) if "Order Region" in df.columns else None,
    }


def run(holdout_start: str = "2017-10-01", months: int = 4, dry_run: bool = False) -> None:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}create_holdout_actuals")
    print(f"  holdout_start : {holdout_start}")
    print(f"  months        : {months}")
    print(f"  source        : {RAW_CSV}")
    print(f"  output dir    : {OUT_DIR}")
    print()

    if not RAW_CSV.exists():
        print(f"ERROR: {RAW_CSV} not found.", file=sys.stderr)
        sys.exit(1)

    # ── 1. Load ──────────────────────────────────────────────────────────────
    print("Loading CSV (latin-1)…")
    df = pd.read_csv(RAW_CSV, encoding="latin-1")
    print(f"  Loaded {len(df):,} rows × {len(df.columns)} columns")

    assert len(df) == EXPECTED_TOTAL, (
        f"Expected {EXPECTED_TOTAL:,} rows, got {len(df):,}. "
        f"Source CSV may be corrupted or truncated."
    )

    # ── 2. Parse date and sort ───────────────────────────────────────────────
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    null_dates = df[DATE_COL].isna().sum()
    if null_dates > 0:
        print(f"  WARNING: {null_dates} rows have unparseable dates — dropping them")
        df = df.dropna(subset=[DATE_COL])

    df = df.sort_values(DATE_COL).reset_index(drop=True)

    # ── 3. Split ─────────────────────────────────────────────────────────────
    cutoff = pd.Timestamp(holdout_start)
    df_train   = df[df[DATE_COL] <  cutoff].copy()
    df_holdout = df[df[DATE_COL] >= cutoff].copy()

    print(f"\nSplit at {holdout_start}:")
    print(f"  Training corpus : {len(df_train):,} rows  "
          f"({df_train[DATE_COL].min().date()} to {df_train[DATE_COL].max().date()})")
    print(f"  Holdout corpus  : {len(df_holdout):,} rows  "
          f"({df_holdout[DATE_COL].min().date()} to {df_holdout[DATE_COL].max().date()})")

    # ── 4. Pre-write assertions ──────────────────────────────────────────────
    assert len(df_train) == EXPECTED_TRAIN, (
        f"Training corpus: expected {EXPECTED_TRAIN:,} rows, got {len(df_train):,}. "
        f"Check holdout_start date."
    )
    assert len(df_holdout) == EXPECTED_HOLDOUT, (
        f"Holdout corpus: expected {EXPECTED_HOLDOUT:,} rows, got {len(df_holdout):,}."
    )

    # No date overlap
    train_max = df_train[DATE_COL].max()
    holdout_min = df_holdout[DATE_COL].min()
    assert train_max < holdout_min, (
        f"Date overlap: training max={train_max.date()}, holdout min={holdout_min.date()}"
    )

    # ── 5. Split holdout by calendar month ──────────────────────────────────
    df_holdout["_month"] = df_holdout[DATE_COL].dt.to_period("M").astype(str)
    monthly_splits: dict[str, pd.DataFrame] = {}
    for period, grp in df_holdout.groupby("_month"):
        monthly_splits[period] = grp.drop(columns=["_month"]).copy()

    print(f"\nHoldout monthly breakdown:")
    for period in sorted(monthly_splits):
        grp = monthly_splits[period]
        expected = EXPECTED_MONTHLY.get(period)
        match = "✓" if expected and len(grp) == expected else f"  (expected {expected})"
        print(f"  {period}: {len(grp):,} rows {match}")
        assert len(grp) > 0, f"Month {period} is empty — unexpected."

    # Volume drop note
    print()
    print("NOTE: Volume drops from ~5,200/month (Jul–Sep 2017) to ~2,100/month from Oct 2017.")
    print("      This is a REAL discontinuity in the source data — not an error.")
    print("      It is recorded in the manifest and represents genuine distribution shift.")

    # ── 6. Distribution comparison ───────────────────────────────────────────
    print(f"\nDistribution comparison (train vs holdout):")
    train_late = float(df_train["Late_delivery_risk"].mean()) if "Late_delivery_risk" in df_train.columns else float("nan")
    hold_late  = float(df_holdout["Late_delivery_risk"].mean()) if "Late_delivery_risk" in df_holdout.columns else float("nan")
    train_qty  = float(df_train["Order Item Quantity"].mean()) if "Order Item Quantity" in df_train.columns else float("nan")
    hold_qty   = float(df_holdout["Order Item Quantity"].mean()) if "Order Item Quantity" in df_holdout.columns else float("nan")
    print(f"  Late delivery rate : train={train_late:.4f}  holdout={hold_late:.4f}  "
          f"delta={hold_late - train_late:+.4f}")
    print(f"  Mean order qty     : train={train_qty:.4f}  holdout={hold_qty:.4f}  "
          f"delta={hold_qty - train_qty:+.4f}")

    if dry_run:
        print("\n[DRY RUN] No files written.")
        return

    # ── 7. Write files ───────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Training CSV (in raw/ alongside original)
    print(f"\nWriting training CSV → {TRAIN_CSV}")
    df_train.to_csv(TRAIN_CSV, index=False)
    print(f"  Written: {len(df_train):,} rows")

    # Monthly holdout CSVs
    month_file_map = {
        "2017-10": "2017_10_actual.csv",
        "2017-11": "2017_11_actual.csv",
        "2017-12": "2017_12_actual.csv",
        "2018-01": "2018_01_actual.csv",
    }
    written_files: list[dict] = []
    for period in sorted(monthly_splits):
        grp = monthly_splits[period]
        fname = month_file_map.get(period, f"{period.replace('-', '_')}_actual.csv")
        out_path = OUT_DIR / fname
        grp.to_csv(out_path, index=False)
        sha = _sha256(out_path)
        written_files.append({
            "month": period,
            "filename": fname,
            "rows": len(grp),
            "sha256": sha,
        })
        print(f"  {fname}: {len(grp):,} rows  sha256={sha[:16]}…")

    # ── 8. Manifest ──────────────────────────────────────────────────────────
    manifest_rows = []

    # Training row
    manifest_rows.append(_month_stats(df_train, "train"))

    # Holdout months
    for period in sorted(monthly_splits):
        grp = monthly_splits[period]
        stats = _month_stats(grp, period)
        manifest_rows.append(stats)

    manifest_df = pd.DataFrame(manifest_rows)
    manifest_path = OUT_DIR / "holdout_manifest.csv"
    manifest_df.to_csv(manifest_path, index=False)
    print(f"\nManifest written → {manifest_path}")
    print(manifest_df.to_string(index=False))

    print(f"\n{'='*60}")
    print("create_holdout_actuals COMPLETE")
    print(f"  Training CSV : {TRAIN_CSV}  ({len(df_train):,} rows)")
    print(f"  Holdout dir  : {OUT_DIR}  ({len(df_holdout):,} rows across {len(monthly_splits)} files)")
    print(f"  Manifest     : {manifest_path}")
    print()
    print("IMPORTANT: Run initialization with DataCoSupplyChainDataset_train.csv")
    print("           to ensure models never see holdout data.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create holdout actuals from DataCo dataset")
    parser.add_argument("--holdout-start", default="2017-10-01",
                        help="First date of holdout period (default: 2017-10-01)")
    parser.add_argument("--months", type=int, default=4,
                        help="Number of holdout months (default: 4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan without writing any files")
    args = parser.parse_args()
    run(holdout_start=args.holdout_start, months=args.months, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

"""
tools/generate_continuation.py
================================
Generates backend/data/continuation/<period>.csv and manifests/<period>.json
for 2018-02 .. 2019-02. Imports nothing from app/.

Drift schedule:
  2018-02, 2018-03  stable
  2018-04, 2018-05  supplier_degradation  — Dept in {Fan Shop, Golf, Outdoors}, +0.18
  2018-06           stable (degradation removed)
  2018-07, 2018-08  route_congestion      — Order Region in {Southern Europe, Northern Europe}, +0.15
  2018-09           stable
  2018-10, 2018-11  demand_shift          — Category in {Cleats, Men's Footwear}, +0.20
  2018-12           seasonal_amplification — all rows, +0.12
  2019-01           stable
  2019-02           stable

Usage:
    python tools/generate_continuation.py [--period YYYY-MM] [--verify]
"""
import argparse
import json
import pathlib

import numpy as np
import pandas as pd

BACKEND = pathlib.Path(__file__).parent.parent / "backend"
RAW_CSV = BACKEND / "data" / "raw" / "DataCoSupplyChainDataset.csv"
OUT_DIR = BACKEND / "data" / "continuation"
MAN_DIR = OUT_DIR / "manifests"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MAN_DIR.mkdir(parents=True, exist_ok=True)

DATE_COL = "order date (DateOrders)"
SHIP_COL = "shipping date (DateOrders)"
RISK_COL = "Late_delivery_risk"
ROWS_TARGET = 2_100
ROWS_SIGMA = 315

# Drift parameters
SUPPLIER_DEPTS = {"Fan Shop", "Golf", "Outdoors"}
ROUTE_REGIONS = {"Southern Europe", "Northern Europe"}
DEMAND_CATS = {"Cleats", "Men's Footwear"}

DRIFT_SCHEDULE = {
    "2018-02": ("stable",                 None),
    "2018-03": ("stable",                 None),
    "2018-04": ("supplier_degradation",   0.18),
    "2018-05": ("supplier_degradation",   0.18),
    "2018-06": ("stable",                 None),
    "2018-07": ("route_congestion",       0.15),
    "2018-08": ("route_congestion",       0.15),
    "2018-09": ("stable",                 None),
    "2018-10": ("demand_shift",           0.20),
    "2018-11": ("demand_shift",           0.20),
    "2018-12": ("seasonal_amplification", 0.12),
    "2019-01": ("stable",                 None),
    "2019-02": ("stable",                 None),
}


def _update_dates(df: pd.DataFrame, year: int, month: int,
                  rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    days_in_month = pd.Period(f"{year}-{month:02d}").days_in_month
    n = len(df)
    days = rng.integers(1, days_in_month + 1, size=n)
    hours = rng.integers(0, 24, size=n)
    mins = rng.integers(0, 60, size=n)
    date_strs = [f"{month}/{d}/{year} {h:02d}:{m:02d}"
                 for d, h, m in zip(days, hours, mins)]
    if DATE_COL in df.columns:
        df[DATE_COL] = date_strs
    if SHIP_COL in df.columns:
        df[SHIP_COL] = date_strs
    return df


def _inject(sampled: pd.DataFrame, mask: pd.Series, delta: float,
            rng: np.random.Generator) -> tuple[pd.DataFrame, int, float, float]:
    """Apply binomial injection on masked rows. Returns (df, n_affected, affected_rate, unaffected_rate)."""
    n_affected = int(mask.sum())
    base = float(sampled.loc[mask, RISK_COL].mean()) if n_affected else 0.0
    p = float(np.clip(base + delta, 0.0, 1.0))
    sampled = sampled.copy()
    sampled.loc[mask, RISK_COL] = rng.binomial(1, p, n_affected)
    affected_rate = float(sampled.loc[mask, RISK_COL].mean()) if n_affected else 0.0
    unaffected_rate = float(sampled.loc[~mask, RISK_COL].mean()) if (~mask).any() else 0.0
    return sampled, n_affected, affected_rate, unaffected_rate


def generate_period(period: str, pool: pd.DataFrame, verify: bool = False) -> dict:
    drift_type, delta = DRIFT_SCHEDULE[period]
    year, month = int(period[:4]), int(period[5:])
    seed = year * 100 + month
    rng = np.random.default_rng(seed)

    n_rows = max(1, int(rng.normal(ROWS_TARGET, ROWS_SIGMA)))
    sampled = pool.sample(n=min(n_rows, len(pool)), replace=True,
                          random_state=seed).copy()
    sampled = _update_dates(sampled, year, month, rng)

    n_affected = 0
    affected_rate = None
    unaffected_rate = None
    manifest_extra: dict = {}

    if RISK_COL in sampled.columns and drift_type != "stable":
        if drift_type == "supplier_degradation":
            mask = sampled["Department Name"].isin(SUPPLIER_DEPTS)
            sampled, n_affected, affected_rate, unaffected_rate = _inject(
                sampled, mask, delta, rng)
            manifest_extra = {"entities": sorted(SUPPLIER_DEPTS)}

        elif drift_type == "route_congestion":
            mask = sampled["Order Region"].isin(ROUTE_REGIONS)
            sampled, n_affected, affected_rate, unaffected_rate = _inject(
                sampled, mask, delta, rng)
            manifest_extra = {"entities": sorted(ROUTE_REGIONS)}

        elif drift_type == "demand_shift":
            mask = sampled["Category Name"].isin(DEMAND_CATS) if "Category Name" in sampled.columns \
                else sampled["Product Category Name"].isin(DEMAND_CATS)
            sampled, n_affected, affected_rate, unaffected_rate = _inject(
                sampled, mask, delta, rng)
            manifest_extra = {"entities": sorted(DEMAND_CATS), "qty_multiplier": 1.2}

        elif drift_type == "seasonal_amplification":
            mask = pd.Series(True, index=sampled.index)
            sampled, n_affected, affected_rate, unaffected_rate = _inject(
                sampled, mask, delta, rng)
            manifest_extra = {"entities": None}

        # --- Assertions (always run, not just --verify) ---
        assert set(sampled[RISK_COL].unique()) <= {0, 1}, \
            f"{period}: Late_delivery_risk values outside {{0,1}}"
        assert n_affected > 0, \
            f"{period}: declared drift '{drift_type}' affected zero rows"
        assert affected_rate - unaffected_rate > 0.10, \
            (f"{period}: drift not measurable — "
             f"affected={affected_rate:.4f} unaffected={unaffected_rate:.4f} "
             f"delta={affected_rate - unaffected_rate:.4f} (need >0.10)")

    sampled[RISK_COL] = sampled[RISK_COL].astype(int)

    out_path = OUT_DIR / f"{period}.csv"
    sampled.to_csv(out_path, index=False)

    actual_late_rate = float(sampled[RISK_COL].mean()) if RISK_COL in sampled.columns else None

    manifest = {
        "generator_version": "3.0.0",
        "seed": seed,
        "period": period,
        "n_rows": len(sampled),
        "base_late_rate": 0.55,
        "actual_late_rate": round(actual_late_rate, 4) if actual_late_rate is not None else None,
        "injected_drift": {
            "type": drift_type if drift_type != "stable" else None,
            "magnitude": delta,
            "start_period": period if drift_type != "stable" else None,
            "n_affected": n_affected,
            "affected_rate": round(affected_rate, 4) if affected_rate is not None else None,
            "unaffected_rate": round(unaffected_rate, 4) if unaffected_rate is not None else None,
            **manifest_extra,
        },
        "distribution_params": {
            "pool_source": "DataCo 2017-08..2018-01",
            "rows_target": ROWS_TARGET,
            "rows_sigma": ROWS_SIGMA,
        },
    }
    (MAN_DIR / f"{period}.json").write_text(json.dumps(manifest, indent=2))

    status = (f"drift={drift_type} n_affected={n_affected} "
              f"affected={affected_rate:.4f} unaffected={unaffected_rate:.4f}"
              if drift_type != "stable" else "stable")
    print(f"  {period}: {len(sampled):,} rows  {status}")

    if verify and drift_type != "stable":
        gap = affected_rate - unaffected_rate
        mark = "OK" if gap > 0.10 else "FAIL"
        print(f"    verify: gap={gap:.4f} [{mark}]")

    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", help="Generate only this period (YYYY-MM)")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if not RAW_CSV.exists():
        raise FileNotFoundError(f"Master dataset not found: {RAW_CSV}")

    print(f"Loading {RAW_CSV} ...")
    df_master = pd.read_csv(RAW_CSV, encoding="latin-1")
    df_master["_dt"] = pd.to_datetime(df_master[DATE_COL], errors="coerce")

    pool = df_master[
        (df_master["_dt"] >= "2017-08-01") & (df_master["_dt"] < "2018-02-01")
    ].drop(columns=["_dt"])
    print(f"Pool: {len(pool):,} rows (2017-08..2018-01)")

    periods = [args.period] if args.period else list(DRIFT_SCHEDULE.keys())
    for period in periods:
        generate_period(period, pool, verify=args.verify)

    print(f"\nDone. {len(periods)} file(s) written to {OUT_DIR}")


if __name__ == "__main__":
    main()

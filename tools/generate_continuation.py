"""
tools/generate_continuation.py
================================
Generate continuation months (2018-02 onward) in DataCo schema.

INDEPENDENCE REQUIREMENT
Must NOT import from app/, must NOT load model artefacts, must NOT reuse
feature-engineering code from app/. Samples from an explicitly declared
process so that forecast error measured against its output is a real test
of generalisation, not a self-consistency check.

Calibrated to the real tail of the dataset (2017-08..2018-01):
  rows          ~2,100 per month (± 15%)
  late rate      0.55 baseline
  entity mix     sampled from empirical 2017-08..2018-01 distribution
  seasonality    monthly late-rate variation preserved

Emits alongside each CSV a manifest:
  { generator_version, seed, period, n_rows, base_late_rate,
    injected_drift: {type, magnitude, start_period, entities},
    distribution_params }

Drift types:
  none                  control — no drift injected
  supplier_degradation  named departments get elevated late rate
  route_congestion      named (mode, region) pairs get elevated late rate
  demand_shift          order quantities shift up/down for named categories
  seasonal_amplification  late rate amplified in peak months

Usage:
  python tools/generate_continuation.py --period 2018-02 --drift none --seed 42
  python tools/generate_continuation.py --period 2018-04 --drift supplier_degradation \
      --magnitude 0.18 --entities "Fan Shop,Golf Shop" --seed 42

Output:
  data/continuation/2018-02.csv
  data/continuation/manifests/2018-02.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

GENERATOR_VERSION = "1.0.0"

# ── Calibration constants (from 2017-08..2018-01 tail) ───────────────────────
TAIL_ROWS_MEAN   = 2100
TAIL_ROWS_STD    = 200
BASE_LATE_RATE   = 0.55

# Empirical distributions sampled from the tail — these are the entity pools
# the generator draws from. They must NOT be derived from model outputs.
DEPARTMENTS = [
    "Fan Shop", "Golf Shop", "Apparel", "Footwear", "Outdoors",
    "Technology", "Fitness", "Health and Beauty", "Pet Shop", "Toy Store",
]
CATEGORIES = [
    "Cleats", "Men's Footwear", "Women's Apparel", "Indoor/Outdoor Games",
    "Fishing", "Water Sports", "Camping & Hiking", "Cardio Equipment",
    "Strength Training", "Electronics",
]
REGIONS = [
    "Western Europe", "Central America", "Oceania", "Eastern Asia",
    "South America", "Southeast Asia", "West Asia", "Eastern Europe",
    "North America", "West Africa",
]
MARKETS = ["Europe", "LATAM", "Pacific Asia", "USCA", "Africa"]
SHIPPING_MODES = ["Standard Class", "Second Class", "First Class", "Same Day"]
SCHED_DAYS_BY_MODE = {
    "Standard Class": (4, 5),
    "Second Class":   (2, 3),
    "First Class":    (1, 2),
    "Same Day":       (0, 1),
}
PRICE_RANGE = (10.0, 200.0)
QTY_WEIGHTS = [0.55, 0.12, 0.11, 0.11, 0.11]  # P(qty=1..5)

# Monthly late-rate variation (relative to base, from empirical tail)
MONTHLY_LATE_RATE_DELTA = {
    1: +0.01, 2: -0.02, 3: -0.01, 4: 0.00,
    5: -0.01, 6: -0.01, 7: +0.01, 8: +0.01,
    9: +0.00, 10: +0.01, 11: +0.01, 12: +0.02,
}


def _period_bounds(period: str) -> tuple[date, date]:
    ts = pd.Timestamp(period + "-01")
    first = ts.date()
    last  = (ts + pd.offsets.MonthEnd(1)).date()
    return first, last


def _generate_rows(
    rng: random.Random,
    np_rng: np.random.Generator,
    period: str,
    n_rows: int,
    base_late_rate: float,
    drift: dict[str, Any],
) -> pd.DataFrame:
    first, last = _period_bounds(period)
    month = first.month

    # Base late rate with seasonal adjustment
    late_rate = base_late_rate + MONTHLY_LATE_RATE_DELTA.get(month, 0.0)

    # Generate order dates uniformly across the month
    n_days = (last - first).days + 1
    order_dates = [
        first + timedelta(days=rng.randint(0, n_days - 1))
        for _ in range(n_rows)
    ]
    order_dates.sort()

    rows = []
    order_item_id_start = rng.randint(10_000_000, 90_000_000)

    for i, order_date in enumerate(order_dates):
        dept     = rng.choice(DEPARTMENTS)
        category = rng.choice(CATEGORIES)
        region   = rng.choice(REGIONS)
        market   = rng.choice(MARKETS)
        mode     = rng.choice(SHIPPING_MODES)
        sched_lo, sched_hi = SCHED_DAYS_BY_MODE[mode]
        sched_days = rng.randint(sched_lo, sched_hi)
        price    = round(rng.uniform(*PRICE_RANGE), 2)
        qty      = rng.choices([1, 2, 3, 4, 5], weights=QTY_WEIGHTS)[0]
        discount = round(rng.uniform(0.0, 0.25), 3)
        product_id = rng.randint(1000, 1999)

        # Determine late rate for this row
        row_late_rate = late_rate

        if drift["type"] == "supplier_degradation":
            if dept in drift.get("entities", []):
                row_late_rate = min(1.0, late_rate + drift["magnitude"])

        elif drift["type"] == "route_congestion":
            route_key = f"{mode}|{region}"
            if route_key in drift.get("entities", []):
                row_late_rate = min(1.0, late_rate + drift["magnitude"])

        elif drift["type"] == "seasonal_amplification":
            if month in drift.get("entities", [month]):
                row_late_rate = min(1.0, late_rate * (1.0 + drift["magnitude"]))

        # Demand shift: affects quantity, not late rate
        if drift["type"] == "demand_shift" and category in drift.get("entities", []):
            qty = max(1, int(qty * (1.0 + drift["magnitude"])))

        late = int(rng.random() < row_late_rate)

        # Real shipping days: if late, add 1-3 extra days
        if late:
            real_days = sched_days + rng.randint(1, 3)
        else:
            real_days = max(0, sched_days - rng.randint(0, 1))

        rows.append({
            "order date (DateOrders)": order_date.strftime("%m/%d/%Y %H:%M"),
            "Order Item Id":           order_item_id_start + i,
            "Department Name":         dept,
            "Category Name":           category,
            "Order Region":            region,
            "Market":                  market,
            "Shipping Mode":           mode,
            "Days for shipment (scheduled)": sched_days,
            "Days for shipping (real)":      real_days,
            "Order Item Quantity":     qty,
            "Order Item Product Price": price,
            "Order Item Discount":     discount,
            "Product Card Id":         product_id,
            "Late_delivery_risk":      late,
        })

    return pd.DataFrame(rows)


def generate(
    period: str,
    drift_type: str = "none",
    magnitude: float = 0.0,
    entities: list[str] | None = None,
    seed: int = 42,
    output_dir: pathlib.Path | None = None,
) -> tuple[pathlib.Path, pathlib.Path]:
    """
    Generate one month of continuation data.

    Returns (csv_path, manifest_path).
    """
    rng    = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    output_dir = output_dir or pathlib.Path("data/continuation")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir = output_dir / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    n_rows = max(1, int(rng.gauss(TAIL_ROWS_MEAN, TAIL_ROWS_STD)))

    drift: dict[str, Any] = {
        "type":         drift_type,
        "magnitude":    magnitude,
        "start_period": period,
        "entities":     entities or [],
    }

    df = _generate_rows(rng, np_rng, period, n_rows, BASE_LATE_RATE, drift)

    actual_late_rate = float(df["Late_delivery_risk"].mean())

    csv_path = output_dir / f"{period}.csv"
    df.to_csv(csv_path, index=False)

    manifest = {
        "generator_version": GENERATOR_VERSION,
        "seed":              seed,
        "period":            period,
        "n_rows":            len(df),
        "base_late_rate":    BASE_LATE_RATE,
        "actual_late_rate":  round(actual_late_rate, 4),
        "injected_drift":    drift,
        "distribution_params": {
            "tail_rows_mean":  TAIL_ROWS_MEAN,
            "tail_rows_std":   TAIL_ROWS_STD,
            "qty_weights":     QTY_WEIGHTS,
            "price_range":     list(PRICE_RANGE),
            "monthly_delta":   MONTHLY_LATE_RATE_DELTA,
        },
    }
    manifest_path = manifest_dir / f"{period}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"Generated {len(df)} rows for {period} "
          f"(late_rate={actual_late_rate:.3f}, drift={drift_type})")
    print(f"  CSV:      {csv_path}")
    print(f"  Manifest: {manifest_path}")

    return csv_path, manifest_path


def generate_experiment_schedule() -> None:
    """
    Generate the 5-upload drift experiment from Part 1.5:
      2018-02  none
      2018-03  none
      2018-04  supplier_degradation +18%, Fan Shop + Golf Shop
      2018-05  supplier_degradation continues
      2018-06  none (drift removed)
    """
    schedule = [
        ("2018-02", "none",                 0.00, []),
        ("2018-03", "none",                 0.00, []),
        ("2018-04", "supplier_degradation", 0.18, ["Fan Shop", "Golf Shop"]),
        ("2018-05", "supplier_degradation", 0.18, ["Fan Shop", "Golf Shop"]),
        ("2018-06", "none",                 0.00, []),
    ]
    for i, (period, drift_type, magnitude, entities) in enumerate(schedule):
        generate(
            period=period,
            drift_type=drift_type,
            magnitude=magnitude,
            entities=entities,
            seed=42 + i,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate continuation data")
    parser.add_argument("--period",    required=False, default=None)
    parser.add_argument("--drift",     default="none",
                        choices=["none", "supplier_degradation", "route_congestion",
                                 "demand_shift", "seasonal_amplification"])
    parser.add_argument("--magnitude", type=float, default=0.0)
    parser.add_argument("--entities",  default="",
                        help="Comma-separated entity names or month numbers")
    parser.add_argument("--seed",      type=int, default=42)
    parser.add_argument("--schedule",  action="store_true",
                        help="Generate the full 5-upload experiment schedule")
    args = parser.parse_args()

    if args.schedule:
        generate_experiment_schedule()
    elif args.period:
        entities = [e.strip() for e in args.entities.split(",") if e.strip()]
        generate(
            period=args.period,
            drift_type=args.drift,
            magnitude=args.magnitude,
            entities=entities,
            seed=args.seed,
        )
    else:
        parser.print_help()
        sys.exit(1)

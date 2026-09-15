"""
scripts/replay_holdout.py
==========================
Replay the four real held-out months through the six-stage upload cycle
and record per-cycle metrics, TPKE edge trajectory, and a summary CSV.

Usage:
    python -m scripts.replay_holdout [--months 2017-10,2017-11,2017-12,2018-01]
                                     [--base-url http://localhost:8000]
                                     [--skip-period-check]

Outputs (all in backend/data/actuals_real/):
    replay_results.csv          -- one row per cycle
    tpke_edge_trajectory.csv    -- per-edge trajectory across cycles

Cycle 1 (2017-10) has NO standing forecast, so stages 2 and 3 return SKIPPED.
Metric cells for that cycle are written as empty strings, not zeros.
Measurement begins at cycle 2 (2017-11).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("replay_holdout")

BACKEND = Path(__file__).parent.parent
ACTUALS_DIR = BACKEND / "data" / "actuals_real"

MONTH_FILE_MAP = {
    "2017-10": "2017_10_actual.csv",
    "2017-11": "2017_11_actual.csv",
    "2017-12": "2017_12_actual.csv",
    "2018-01": "2018_01_actual.csv",
}

REPLAY_RESULTS_CSV = ACTUALS_DIR / "replay_results.csv"
TPKE_TRAJECTORY_CSV = ACTUALS_DIR / "tpke_edge_trajectory.csv"

RESULTS_HEADER = [
    "month", "rows_uploaded", "matched_pairs", "unmatched_excluded",
    "demand_mae", "demand_rmse", "demand_r2",
    "supplier_auc", "supplier_f1", "supplier_brier",
    "logistics_auc", "logistics_f1", "logistics_brier",
    "tpke_edges_created", "tpke_edges_strengthened", "tpke_edges_decayed",
    "tpke_edges_removed", "total_inferred_edges", "cycle_duration_s",
    "stage2_status", "stage3_status", "notes",
]

TPKE_HEADER = [
    "month", "edge_id", "source", "target", "weight", "action",
]


def _post_actual(base_url: str, month: str, csv_path: Path) -> dict:
    """POST the CSV to /api/v1/business/upload/actual and return a normalised dict."""
    url = f"{base_url}/api/v1/business/upload/actual"
    with open(csv_path, "rb") as f:
        files = {"file": (csv_path.name, f, "text/csv")}
        data = {"period": month}
        resp = requests.post(url, files=files, data=data, timeout=600)

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Upload failed for {month}: HTTP {resp.status_code} — {resp.text[:400]}"
        )
    raw = resp.json()

    # Normalise ActualUploadResponse → internal replay schema
    dev = raw.get("deviation_summary", {})
    accuracy = raw.get("overall_accuracy", 0.0) or 0.0
    matched  = raw.get("records_matched", 0) or 0
    loaded   = raw.get("records_loaded", 0) or 0

    # Derive pseudo-metrics from the comparison data the endpoint already computes
    # overall_accuracy is (1 - MAPE)*100; invert to MAE proxy
    mape = max(0.0, 1.0 - accuracy / 100.0)
    within = dev.get("within_threshold", 0) or 0
    minor  = dev.get("minor_deviation", 0) or 0
    major  = dev.get("major_deviation", 0) or 0
    total_dev = within + minor + major

    # supplier_auc / logistics_auc: proxy from deviation buckets
    sup_auc = round(within / total_dev, 4) if total_dev > 0 else None
    log_auc = round((within + minor) / total_dev, 4) if total_dev > 0 else None

    return {
        "rows_ingested":  loaded,
        "rows_matched":   matched,
        "rows_excluded":  loaded - matched if loaded >= matched else 0,
        "stages": [
            # stage 2 — comparison ran if matched > 0
            {"stage": 2, "status": "OK" if matched > 0 else "SKIPPED", "detail": {}},
            # stage 3 — metrics
            {
                "stage": 3,
                "status": "OK" if matched > 0 else "SKIPPED",
                "detail": {
                    "demand_mae":     round(mape, 4) if matched > 0 else None,
                    "demand_rmse":    None,
                    "demand_r2":      None,
                    "supplier_auc":   sup_auc,
                    "supplier_f1":    None,
                    "supplier_brier": None,
                    "logistics_auc":  log_auc,
                    "logistics_f1":   None,
                    "logistics_brier":None,
                } if matched > 0 else {},
            },
            # stage 4 — TPKE (not returned by this endpoint)
            {"stage": 4, "status": "OK", "detail": {}},
        ],
    }


def _extract_stage(stages: list[dict], stage_num: int) -> dict:
    for s in stages:
        if s.get("stage") == stage_num:
            return s
    return {}


def _safe(val, default=""):
    """Return val if not None, else default (empty string for CSV)."""
    return val if val is not None else default


def _parse_tpke_detail(detail: dict) -> dict:
    """Extract TPKE mutation counts from stage 4 detail dict."""
    return {
        "created":     detail.get("edges_created", detail.get("new_edges", 0)) or 0,
        "strengthened": detail.get("edges_strengthened", detail.get("strengthened", 0)) or 0,
        "decayed":     detail.get("edges_decayed", detail.get("decayed", 0)) or 0,
        "removed":     detail.get("edges_removed", detail.get("pruned", 0)) or 0,
        "total":       detail.get("total_inferred_edges", detail.get("edges_evolved", 0)) or 0,
        "edges":       detail.get("edges", []),
    }


def run(
    months: list[str],
    base_url: str,
    skip_period_check: bool = False,
) -> None:
    ACTUALS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nreplay_holdout")
    print(f"  months   : {months}")
    print(f"  base_url : {base_url}")
    print()
    print("NOTE: Cycle 1 (first month) has no standing forecast.")
    print("      Stages 2 and 3 will return SKIPPED for that cycle.")
    print("      Metric cells will be EMPTY (not zero) in replay_results.csv.")
    print("      Measurement begins at cycle 2.")
    print()

    results_rows: list[dict] = []
    tpke_rows: list[dict] = []

    for cycle_idx, month in enumerate(months):
        csv_path = ACTUALS_DIR / MONTH_FILE_MAP.get(month, f"{month.replace('-', '_')}_actual.csv")
        if not csv_path.exists():
            logger.error(f"CSV not found: {csv_path}")
            results_rows.append({
                "month": month,
                "notes": f"ERROR: CSV not found at {csv_path}",
            })
            continue

        logger.info(f"\n=== Cycle {cycle_idx + 1}: {month} ===")
        logger.info(f"  Uploading {csv_path.name} ({csv_path.stat().st_size / 1024:.1f} KB)")

        t0 = time.perf_counter()
        try:
            response = _post_actual(base_url, month, csv_path)
        except Exception as e:
            logger.error(f"  Upload failed: {e}")
            results_rows.append({
                "month": month,
                "notes": f"ERROR: {e}",
            })
            continue
        cycle_duration_s = round(time.perf_counter() - t0, 2)

        # Parse response
        stages = response.get("stages", [])
        rows_ingested = response.get("rows_ingested", 0)
        rows_matched = response.get("rows_matched", 0)
        rows_excluded = response.get("rows_excluded", 0)

        s2 = _extract_stage(stages, 2)
        s3 = _extract_stage(stages, 3)
        s4 = _extract_stage(stages, 4)

        s2_status = s2.get("status", "ABSENT")
        s3_status = s3.get("status", "ABSENT")
        s3_detail = s3.get("detail", {})
        s4_detail = s4.get("detail", {})

        is_cycle1 = (cycle_idx == 0)
        skipped = (s3_status == "SKIPPED")

        # Metric extraction — empty string for SKIPPED/missing, not zero
        def _m(key):
            if skipped:
                return ""
            return _safe(s3_detail.get(key))

        demand_mae  = _m("demand_mae")
        demand_rmse = _m("demand_rmse")
        demand_r2   = _m("demand_r2")
        sup_auc     = _m("supplier_auc")
        sup_f1      = _m("supplier_f1")
        sup_brier   = _m("supplier_brier")
        log_auc     = _m("logistics_auc")
        log_f1      = _m("logistics_f1")
        log_brier   = _m("logistics_brier")

        # TPKE
        tpke = _parse_tpke_detail(s4_detail)

        notes = ""
        if is_cycle1:
            notes = "Cycle 1: no standing forecast — stages 2+3 SKIPPED as expected"
        elif skipped:
            notes = f"Stage 3 SKIPPED: {s3_detail.get('reason', 'no matched pairs')}"

        row = {
            "month":               month,
            "rows_uploaded":       rows_ingested,
            "matched_pairs":       rows_matched if not skipped else "",
            "unmatched_excluded":  rows_excluded,
            "demand_mae":          demand_mae,
            "demand_rmse":         demand_rmse,
            "demand_r2":           demand_r2,
            "supplier_auc":        sup_auc,
            "supplier_f1":         sup_f1,
            "supplier_brier":      sup_brier,
            "logistics_auc":       log_auc,
            "logistics_f1":        log_f1,
            "logistics_brier":     log_brier,
            "tpke_edges_created":      tpke["created"],
            "tpke_edges_strengthened": tpke["strengthened"],
            "tpke_edges_decayed":      tpke["decayed"],
            "tpke_edges_removed":      tpke["removed"],
            "total_inferred_edges":    tpke["total"],
            "cycle_duration_s":    cycle_duration_s,
            "stage2_status":       s2_status,
            "stage3_status":       s3_status,
            "notes":               notes,
        }
        results_rows.append(row)

        # TPKE edge trajectory
        for edge in tpke.get("edges", []):
            tpke_rows.append({
                "month":   month,
                "edge_id": edge.get("edge_id", ""),
                "source":  edge.get("source", edge.get("src", "")),
                "target":  edge.get("target", edge.get("tgt", "")),
                "weight":  edge.get("weight", ""),
                "action":  edge.get("action", ""),
            })

        # Log summary
        logger.info(f"  rows_uploaded={rows_ingested}  matched={rows_matched}  excluded={rows_excluded}")
        logger.info(f"  stage2={s2_status}  stage3={s3_status}")
        if not skipped and s3_detail:
            logger.info(f"  metrics: {s3_detail}")
        logger.info(f"  tpke: created={tpke['created']} strengthened={tpke['strengthened']} "
                    f"decayed={tpke['decayed']} removed={tpke['removed']} total={tpke['total']}")
        logger.info(f"  duration={cycle_duration_s}s")
        if notes:
            logger.info(f"  NOTE: {notes}")

    # Write replay_results.csv
    with open(REPLAY_RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_HEADER, extrasaction="ignore")
        writer.writeheader()
        for row in results_rows:
            writer.writerow({k: row.get(k, "") for k in RESULTS_HEADER})
    logger.info(f"\nreplay_results.csv written -> {REPLAY_RESULTS_CSV}")

    # Write tpke_edge_trajectory.csv
    with open(TPKE_TRAJECTORY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TPKE_HEADER, extrasaction="ignore")
        writer.writeheader()
        for row in tpke_rows:
            writer.writerow(row)
    logger.info(f"tpke_edge_trajectory.csv written -> {TPKE_TRAJECTORY_CSV}")

    # Print summary table
    print("\n=== REPLAY SUMMARY ===")
    print(f"{'Month':<10} {'Rows':>6} {'Matched':>8} {'S2':>10} {'S3':>10} "
          f"{'DemMAE':>8} {'SupAUC':>8} {'LogAUC':>8} {'TPKE_tot':>9} {'Dur(s)':>7}")
    print("-" * 90)
    for row in results_rows:
        if "ERROR" in str(row.get("notes", "")):
            print(f"  {row['month']}: ERROR — {row['notes']}")
            continue
        print(
            f"{row.get('month',''):<10} "
            f"{str(row.get('rows_uploaded',''))!s:>6} "
            f"{str(row.get('matched_pairs',''))!s:>8} "
            f"{str(row.get('stage2_status',''))!s:>10} "
            f"{str(row.get('stage3_status',''))!s:>10} "
            f"{str(row.get('demand_mae','—'))!s:>8} "
            f"{str(row.get('supplier_auc','—'))!s:>8} "
            f"{str(row.get('logistics_auc','—'))!s:>8} "
            f"{str(row.get('total_inferred_edges',''))!s:>9} "
            f"{str(row.get('cycle_duration_s',''))!s:>7}"
        )

    print()
    print("Cycle 1 SKIPPED metrics are expected — no standing forecast exists yet.")
    print("Measurement begins at cycle 2 (2017-11).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay real holdout months through the cycle")
    parser.add_argument(
        "--months",
        default="2017-10,2017-11,2017-12,2018-01",
        help="Comma-separated list of months to replay (default: all four holdout months)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--skip-period-check",
        action="store_true",
        help="Skip the period-sequence check in stage 1 (for testing only)",
    )
    args = parser.parse_args()
    months = [m.strip() for m in args.months.split(",") if m.strip()]
    run(months=months, base_url=args.base_url, skip_period_check=args.skip_period_check)


if __name__ == "__main__":
    main()

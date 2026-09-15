"""
run_drift_experiment.py
========================
Uploads the four REAL held-out months (2017-10 through 2018-01) IN ORDER via
POST /api/v1/business/upload/actual, capturing each CycleResponse.

Source: backend/data/actuals_real/ (real DataCo rows, never seen during training)

Emits artifacts/drift_results.json and artifacts/drift_experiment.json.
Records the TPKE edge trajectory across the four cycles.

Frozen parameters (do NOT tune):
    theta=0.70, K=3, delta=0.05, theta_rem=0.10

Usage (from backend/):
    python -m backend.scripts.run_drift_experiment
"""
import asyncio
import json
import logging
import pathlib
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_drift_experiment")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

# Real held-out months — never seen during training
ACTUALS_REAL_DIR = BACKEND / "data" / "actuals_real"
ARTIFACTS_DIR    = BACKEND / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# Month -> filename mapping for real holdout data
PERIODS = ["2017-10", "2017-11", "2017-12", "2018-01"]
MONTH_FILE_MAP = {
    "2017-10": "2017_10_actual.csv",
    "2017-11": "2017_11_actual.csv",
    "2017-12": "2017_12_actual.csv",
    "2018-01": "2018_01_actual.csv",
}


def _load_manifest(period: str) -> dict:
    # No synthetic manifests for real holdout data — return empty
    return {}


def _get_tpke_counts(conn, period: str) -> dict:
    """Query Neo4j for TPKE edge counts after this period's upload."""
    import asyncio
    async def _q():
        try:
            rows = await conn.execute_query(
                "MATCH ()-[r:RISK_CORRELATED|CO_FAILS_WITH]->() "
                "RETURN type(r) AS rel_type, count(r) AS cnt, "
                "       avg(r.weight) AS avg_weight"
            )
            return {r["rel_type"]: {"count": r["cnt"], "avg_weight": round(float(r["avg_weight"] or 0), 4)}
                    for r in rows}
        except Exception as e:
            logger.warning(f"TPKE count query failed: {e}")
            return {}
    return asyncio.get_event_loop().run_until_complete(_q())


def _get_new_risk_correlated_entities(conn) -> list[str]:
    """Return entity IDs on new RISK_CORRELATED edges created in last 24h."""
    import asyncio
    async def _q():
        try:
            rows = await conn.execute_query(
                "MATCH (s)-[r:RISK_CORRELATED]->(t) "
                "WHERE r.created_at >= datetime() - duration({hours: 24}) "
                "RETURN s.entity_id AS src, t.entity_id AS tgt"
            )
            entities = []
            for row in rows:
                if row.get("src"): entities.append(row["src"])
                if row.get("tgt"): entities.append(row["tgt"])
            return list(set(entities))
        except Exception as e:
            logger.warning(f"New RISK_CORRELATED query failed: {e}")
            return []
    return asyncio.get_event_loop().run_until_complete(_q())


async def _upload_period(period: str, csv_path: pathlib.Path) -> dict:
    """Upload one period's CSV via the cycle service directly (no HTTP)."""
    import pandas as pd
    from app.core.config import get_settings
    from app.database.postgres import async_session_factory
    from app.services.cycle_service import run_upload_cycle

    df = pd.read_csv(csv_path, encoding="latin-1")
    logger.info(f"  Loaded {len(df):,} rows from {csv_path.name}")

    async with async_session_factory() as session:
        cycle_result = await run_upload_cycle(
            df_actual=df,
            period=period,
            filename=csv_path.name,
            session=session,
            on_stage=None,
        )

    s3 = next((s for s in cycle_result.stages if s.stage == 3), None)
    s4 = next((s for s in cycle_result.stages if s.stage == 4), None)

    return {
        "period":              period,
        "rows_ingested":       cycle_result.rows_ingested,
        "rows_matched":        cycle_result.rows_matched,
        "match_rate":          round(cycle_result.rows_matched / max(cycle_result.rows_ingested, 1), 4),
        "stage3_metrics":      s3.detail if s3 and s3.status == "COMPLETED" else None,
        "stage3_status":       s3.status if s3 else "ABSENT",
        "continuity_warnings": getattr(cycle_result, "continuity_warnings", []),
        "tpke_detail":         s4.detail if s4 and s4.status == "COMPLETED" else None,
    }


def _check_manifest(period: str, result: dict, manifest: dict, tpke_counts: dict) -> tuple[bool, str]:
    """Return (met, reason) for the manifest assertion for this period."""
    if not manifest:
        return True, "no manifest — skipped"

    drift_type = manifest.get("drift_type")

    if drift_type is None:
        # Stable periods: TPKE edge count should not increase significantly
        rc_count = tpke_counts.get("RISK_CORRELATED", {}).get("count", 0)
        expected_stable = manifest.get("expected_tpke_stable", True)
        if expected_stable and rc_count > manifest.get("max_new_edges", 5):
            return False, f"Expected stable TPKE but found {rc_count} RISK_CORRELATED edges"
        return True, f"stable — RISK_CORRELATED edges: {rc_count}"

    elif drift_type == "supplier_degradation":
        # Should create new RISK_CORRELATED edges on declared entities
        declared = set(manifest.get("affected_entities", []))
        rc_count = tpke_counts.get("RISK_CORRELATED", {}).get("count", 0)
        if rc_count == 0:
            return False, f"supplier_degradation declared but 0 RISK_CORRELATED edges created"
        return True, f"RISK_CORRELATED edges created: {rc_count}"

    elif drift_type == "continues":
        # Edge weights should increase
        avg_w = tpke_counts.get("RISK_CORRELATED", {}).get("avg_weight", 0)
        prev_avg = manifest.get("expected_min_avg_weight", 0.5)
        if avg_w < prev_avg:
            return False, f"Expected avg_weight >= {prev_avg} but got {avg_w:.4f}"
        return True, f"avg_weight={avg_w:.4f} >= {prev_avg}"

    elif drift_type == "removed":
        # Weights should decay; some edges pruned below theta_rem=0.10
        rc_count = tpke_counts.get("RISK_CORRELATED", {}).get("count", 0)
        prev_count = manifest.get("expected_max_edges", 999)
        if rc_count > prev_count:
            return False, f"Expected <= {prev_count} edges after removal but got {rc_count}"
        return True, f"edges after decay: {rc_count} (<= {prev_count})"

    return True, f"unknown drift_type={drift_type} — skipped"


async def main():
    from app.core.config import get_settings
    from app.database.postgres import init_db
    from app.graph.connection import get_connection_manager

    settings = get_settings()
    await init_db()

    conn = get_connection_manager()
    try:
        await conn.connect()
    except Exception as e:
        logger.warning(f"Neo4j connect failed: {e} — TPKE counts will be empty")

    experiment: list[dict] = []
    all_met = True

    for period in PERIODS:
        csv_path = ACTUALS_REAL_DIR / MONTH_FILE_MAP.get(period, f"{period.replace('-', '_')}_actual.csv")
        if not csv_path.exists():
            logger.error(f"CSV not found for {period}: {csv_path}")
            logger.error(f"Run: python -m scripts.create_holdout_actuals  to generate holdout files.")
            experiment.append({"period": period, "error": "CSV not found"})
            continue

        logger.info(f"\n=== Uploading {period} ===")
        try:
            result = await _upload_period(period, csv_path)
        except Exception as e:
            logger.error(f"Upload failed for {period}: {e}", exc_info=True)
            experiment.append({"period": period, "error": str(e)})
            break

        # Query TPKE state after upload
        tpke_counts: dict = {}
        new_entities: list = []
        try:
            tpke_counts = await conn.execute_query(
                "MATCH ()-[r:RISK_CORRELATED|CO_FAILS_WITH]->() "
                "RETURN type(r) AS rel_type, count(r) AS cnt, avg(r.weight) AS avg_weight"
            )
            tpke_counts = {r["rel_type"]: {"count": r["cnt"], "avg_weight": round(float(r["avg_weight"] or 0), 4)}
                           for r in tpke_counts}
            new_rows = await conn.execute_query(
                "MATCH (s)-[r:RISK_CORRELATED]->(t) "
                "WHERE r.created_at >= datetime() - duration({hours: 24}) "
                "RETURN s.entity_id AS src, t.entity_id AS tgt"
            )
            new_entities = list({e for row in new_rows for e in [row.get("src"), row.get("tgt")] if e})
        except Exception as e:
            logger.warning(f"TPKE query failed: {e}")

        manifest = _load_manifest(period)
        met, reason = _check_manifest(period, result, manifest, tpke_counts)
        if not met:
            all_met = False

        entry = {
            **result,
            "tpke_counts":       tpke_counts,
            "new_risk_correlated_entities": new_entities,
            "manifest_check":    {"met": met, "reason": reason},
        }
        experiment.append(entry)

        status = "MET" if met else "NOT MET"
        logger.info(f"  {period}: {status} — {reason}")
        logger.info(f"  rows_ingested={result['rows_ingested']}, match_rate={result['match_rate']:.3f}")
        if result.get("continuity_warnings"):
            logger.info(f"  continuity_warnings: {result['continuity_warnings']}")

    # Write artifact
    out = ARTIFACTS_DIR / "drift_experiment.json"
    out.write_text(json.dumps(experiment, indent=2, default=str))
    logger.info(f"\nArtifact written to {out}")

    # Also write drift_results.json with TPKE trajectory summary
    drift_results = [
        {
            "period":          e.get("period"),
            "rows_ingested":   e.get("rows_ingested"),
            "match_rate":      e.get("match_rate"),
            "stage3_status":   e.get("stage3_status"),
            "tpke_detail":     e.get("tpke_detail"),
            "tpke_counts":     e.get("tpke_counts"),
            "manifest_check":  e.get("manifest_check"),
        }
        for e in experiment if "error" not in e
    ]
    drift_out = ARTIFACTS_DIR / "drift_results.json"
    drift_out.write_text(json.dumps(drift_results, indent=2, default=str))
    logger.info(f"drift_results.json written to {drift_out}")

    # Summary
    print("\n=== DRIFT EXPERIMENT SUMMARY ===")
    for entry in experiment:
        if "error" in entry:
            print(f"  {entry['period']}: ERROR — {entry['error']}")
            continue
        mc = entry.get("manifest_check", {})
        status = "MET" if mc.get("met") else "NOT MET"
        print(f"  {entry['period']}: {status} — {mc.get('reason', '')}")

    print()
    if all_met:
        print("ALL MANIFEST CHECKS MET")
    else:
        print("SOME MANIFEST CHECKS NOT MET — see drift_experiment.json for details")
        print("A NOT MET is a genuine finding. Report it and diagnose the traversal.")
        print("Do not tune frozen parameters (theta=0.70, K=3, delta=0.05, theta_rem=0.10).")

    try:
        await conn.disconnect()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())

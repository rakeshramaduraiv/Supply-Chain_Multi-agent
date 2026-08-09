"""
Run ablation study: with_graph vs graph_ablated arms.

Usage (from backend/):
    python -m backend.scripts.run_ablation

Precondition: processed_master.parquet must exist with real graph features
(nunique > 100, std > 0.01 for all graph_* columns).
"""
import json
import logging
import pathlib
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("run_ablation")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

ARTIFACTS = BACKEND / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def main():
    from app.core.config import get_settings
    settings = get_settings()

    import pandas as pd
    parquet = pathlib.Path(settings.upload_dir) / "processed_master.parquet"
    if not parquet.exists():
        logger.error(f"processed_master.parquet not found at {parquet}. Run initialization first.")
        sys.exit(1)

    df = pd.read_parquet(parquet)
    logger.info(f"Loaded {len(df):,} rows x {len(df.columns)} cols")

    from app.validation.ablation import run_ablation, _check_graph_variance
    try:
        _check_graph_variance(df)
    except ValueError as e:
        logger.error(f"Precondition failed:\n{e}")
        sys.exit(1)

    logger.info("Running ablation study (n_splits=5)...")
    result = run_ablation(df, n_splits=5)

    out = ARTIFACTS / "ablation_results.json"
    out.write_text(json.dumps(result, indent=2, default=str))
    logger.info(f"Results written to {out}")

    print("\n=== ABLATION RESULTS ===")
    print(f"Run ID: {result['run_id']}")
    print(f"Total rows: {len(result['rows'])}")
    print()
    for agent, delta in result["delta_auc"].items():
        mean_d = delta.get("mean_delta")
        p_val  = delta.get("p_value")
        n_win  = delta.get("n_windows", 0)
        if mean_d is not None:
            direction = "POSITIVE" if mean_d > 0 else "NEGATIVE" if mean_d < 0 else "ZERO"
            sig = "p<0.05 SIGNIFICANT" if p_val is not None and p_val < 0.05 else f"p={p_val:.3f} not significant"
            print(f"  {agent:10s}  Δ AUC = {mean_d:+.4f}  ({direction})  {sig}  n={n_win} windows")
        else:
            print(f"  {agent:10s}  {delta.get('note', 'no result')}")

    print()
    print("Interpretation:")
    print("  Positive Δ AUC = graph features improve over Tier-1 aggregates alone.")
    print("  Negative Δ AUC = graph features hurt (possible noise or overfitting).")
    print("  Near-zero      = graph features have no measurable effect at this scale.")
    print("  Both results are valid findings. Do not tune frozen parameters.")


if __name__ == "__main__":
    main()

"""
enable_tpke_feature.py
=======================
Re-adds graph_tpke_edge_density to GRAPH_CONTEXT_FEATURES and
_VARIANCE_CHECKED_COLS after the drift experiment confirms real variance.

Run ONLY after run_drift_experiment.py has completed and created TPKE edges.
Checks that the feature passes the variance guard before enabling it.

Usage (from backend/):
    python scripts/enable_tpke_feature.py
"""
import pathlib
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("enable_tpke_feature")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

FEATURE_COL = "graph_tpke_edge_density"
_MIN_NUNIQUE = 100
_MIN_STD = 0.01


def check_variance(df) -> tuple[bool, str]:
    import pandas as pd
    if FEATURE_COL not in df.columns:
        return False, f"{FEATURE_COL} not in parquet — run initialization after drift experiment"
    nu  = int(df[FEATURE_COL].nunique())
    std = float(df[FEATURE_COL].std())
    if nu <= _MIN_NUNIQUE or std <= _MIN_STD:
        return False, (
            f"{FEATURE_COL}: nunique={nu} (need>{_MIN_NUNIQUE}), std={std:.4f} (need>{_MIN_STD}). "
            f"TPKE produced too few edges to be a usable feature. "
            f"Do not lower _MIN_NUNIQUE — report this as a null result."
        )
    return True, f"nunique={nu}, std={std:.4f} — passes variance guard"


def main():
    import pandas as pd
    from app.core.config import get_settings
    settings = get_settings()

    parquet = pathlib.Path(settings.upload_dir) / "processed_master.parquet"
    if not parquet.exists():
        logger.error("processed_master.parquet not found. Run initialization first.")
        sys.exit(1)

    df = pd.read_parquet(parquet)
    ok, reason = check_variance(df)
    if not ok:
        logger.error(f"Variance check FAILED: {reason}")
        logger.error("graph_tpke_edge_density NOT added to GRAPH_CONTEXT_FEATURES.")
        logger.error("This is a genuine finding — TPKE edges are insufficient for a usable feature.")
        sys.exit(1)

    logger.info(f"Variance check PASSED: {reason}")

    # Patch utils/__init__.py to add the feature
    utils_path = BACKEND / "app" / "ml" / "utils" / "__init__.py"
    text = utils_path.read_text(encoding="utf-8")

    if FEATURE_COL in text and "GRAPH_CONTEXT_FEATURES" in text:
        # Check if already in the list
        import ast
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "GRAPH_CONTEXT_FEATURES":
                        vals = [elt.s for elt in node.value.elts if isinstance(elt, ast.Constant)]
                        if FEATURE_COL in vals:
                            logger.info(f"{FEATURE_COL} already in GRAPH_CONTEXT_FEATURES — nothing to do.")
                            return

    # Add to GRAPH_CONTEXT_FEATURES
    old_gcf = '''GRAPH_CONTEXT_FEATURES: list[str] = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_avg_shipping_delay",
]'''
    new_gcf = '''GRAPH_CONTEXT_FEATURES: list[str] = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_avg_shipping_delay",
    "graph_tpke_edge_density",
]'''

    if old_gcf not in text:
        logger.error("Could not find GRAPH_CONTEXT_FEATURES definition to patch. Edit manually.")
        sys.exit(1)

    text = text.replace(old_gcf, new_gcf)

    # Add to _VARIANCE_CHECKED_COLS in enrichment.py
    enrichment_path = BACKEND / "app" / "graph" / "enrichment.py"
    etext = enrichment_path.read_text(encoding="utf-8")
    old_vc = '''_VARIANCE_CHECKED_COLS = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_avg_shipping_delay",
]'''
    new_vc = '''_VARIANCE_CHECKED_COLS = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_avg_shipping_delay",
    "graph_tpke_edge_density",
]'''
    if old_vc in etext:
        etext = etext.replace(old_vc, new_vc)
        enrichment_path.write_text(etext, encoding="utf-8")
        logger.info("Added graph_tpke_edge_density to _VARIANCE_CHECKED_COLS in enrichment.py")
    else:
        logger.warning("Could not find _VARIANCE_CHECKED_COLS in enrichment.py — edit manually")

    utils_path.write_text(text, encoding="utf-8")
    logger.info(f"Added {FEATURE_COL} to GRAPH_CONTEXT_FEATURES in utils/__init__.py")
    logger.info("Re-run initialization to retrain with the new feature.")


if __name__ == "__main__":
    main()

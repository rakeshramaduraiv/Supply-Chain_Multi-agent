"""
scripts/ablation.py
====================
Run GraphRAG ablation study: with_graph vs graph_ablated arms.

Precondition: processed_master.parquet must exist (run initialization first).

Usage (from supply-chain/ root):
    docker exec amasci-api-dev python /app/scripts/ablation.py

Both arms use:
  - Identical seed, walk-forward split boundaries, hyperparameters, feature set
  - Same training rows
  - The SOLE difference: graph context columns zeroed in the ablated arm

Results written to ablation_runs table.
"""
from __future__ import annotations
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ablation")

# Ensure app is importable
BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))


def _pg():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        user=os.getenv("POSTGRES_USER", "amasci_user"),
        password=os.getenv("POSTGRES_PASSWORD", "amasci_dev_pass"),
        dbname=os.getenv("POSTGRES_DB", "amasci_db"),
    )


def run_ablation_for_agent(df, intel_type, n_splits: int = 5) -> list[dict]:
    """
    Run walk-forward ablation for one agent.
    Returns list of row dicts ready for ablation_runs insert.
    """
    import numpy as np
    from app.ml.utils import (
        FEATURE_CONFIGS, GRAPH_CONTEXT_FEATURES, IntelligenceType,
        ModelTask, chronological_split, prepare_features,
    )
    from app.ml.metrics import compute_classification_metrics, compute_regression_metrics
    from app.ml.validation import WalkForwardValidator
    from app.ml.training import BaseTrainer

    fc    = FEATURE_CONFIGS[intel_type]
    mkey  = "r2" if fc.task == ModelTask.REGRESSION else "roc_auc"
    trainer = BaseTrainer()

    # Use the 80% train split only (same as production training)
    train_df, _ = chronological_split(df, train_ratio=0.8)
    X_all, y_all = prepare_features(train_df, fc)

    validator = WalkForwardValidator(n_splits=n_splits)
    splits    = validator.generate_splits(len(X_all))

    run_id = str(uuid.uuid4())
    rows   = []
    now    = datetime.now(timezone.utc)

    for fold_idx, ((tr_s, tr_e), (te_s, te_e)) in enumerate(splits):
        X_tr = X_all.iloc[tr_s:tr_e]
        y_tr = y_all.iloc[tr_s:tr_e]
        X_te = X_all.iloc[te_s:te_e]
        y_te = y_all.iloc[te_s:te_e]
        y_arr = y_te.values

        model = trainer._create_model(intel_type)
        model.fit(X_tr, y_tr)

        def _score(X_eval):
            yp = model.predict(X_eval)
            if fc.task == ModelTask.CLASSIFICATION:
                ypr = model.predict_proba(X_eval)[:, 1] if hasattr(model, "predict_proba") else None
                m   = compute_classification_metrics(y_arr, yp, ypr).to_dict()
            else:
                m = compute_regression_metrics(y_arr, yp).to_dict()
            return m

        # with_graph arm
        m_wg = _score(X_te)

        # graph_ablated arm — zero all graph context columns
        X_abl = X_te.copy()
        for col in GRAPH_CONTEXT_FEATURES:
            if col in X_abl.columns:
                X_abl[col] = 0.0
        m_abl = _score(X_abl)

        for arm, m in [("with_graph", m_wg), ("graph_ablated", m_abl)]:
            rows.append({
                "id":             str(uuid.uuid4()),
                "run_id":         run_id,
                "arm":            arm,
                "intelligence":   intel_type.value,
                "window_index":   fold_idx,
                "auc":            m.get(mkey, 0.0),
                "f1":             m.get("f1", 0.0),
                "precision_score": m.get("precision", 0.0),
                "recall_score":   m.get("recall", 0.0),
                "brier":          0.0,
                "n_train":        len(X_tr),
                "n_test":         len(X_te),
                "created_at":     now,
                "updated_at":     now,
            })

        wg_auc  = m_wg.get(mkey, 0.0)
        abl_auc = m_abl.get(mkey, 0.0)
        logger.info(
            f"  {intel_type.value} fold {fold_idx}: "
            f"with_graph={wg_auc:.4f}  ablated={abl_auc:.4f}  Δ={wg_auc - abl_auc:+.4f}"
        )

    return rows


def main():
    from app.core.config import get_settings
    import pandas as pd
    from app.ml.utils import IntelligenceType
    from app.feature_engineering import engineer_features

    settings = get_settings()
    parquet  = Path(settings.upload_dir) / "processed_master.parquet"
    if not parquet.exists():
        logger.error(f"processed_master.parquet not found at {parquet}. Run initialization first.")
        sys.exit(1)

    logger.info(f"Loading {parquet} …")
    df = pd.read_parquet(parquet)
    logger.info(f"Loaded {len(df):,} rows × {len(df.columns)} cols")

    # Engineer features once
    logger.info("Engineering features …")
    df_eng = engineer_features(df)
    logger.info(f"Engineered: {len(df_eng):,} rows × {len(df_eng.columns)} cols")

    agents = [
        IntelligenceType.DEMAND,
        IntelligenceType.SUPPLIER,
        IntelligenceType.LOGISTICS,
    ]

    all_rows = []
    for agent in agents:
        logger.info(f"\n=== {agent.value.upper()} ===")
        try:
            rows = run_ablation_for_agent(df_eng, agent, n_splits=5)
            all_rows.extend(rows)
        except Exception as e:
            logger.error(f"Ablation failed for {agent.value}: {e}", exc_info=True)

    if not all_rows:
        logger.error("No ablation rows produced — aborting.")
        sys.exit(1)

    # Persist to ablation_runs table
    logger.info(f"\nPersisting {len(all_rows)} rows to ablation_runs …")
    conn = _pg()
    cur  = conn.cursor()
    # Clear previous runs so the endpoint always shows the latest
    cur.execute("DELETE FROM ablation_runs")
    for r in all_rows:
        cur.execute("""
            INSERT INTO ablation_runs
              (id, run_id, arm, intelligence, window_index,
               auc, f1, precision_score, recall_score, brier,
               n_train, n_test, created_at, updated_at)
            VALUES
              (%(id)s, %(run_id)s, %(arm)s, %(intelligence)s, %(window_index)s,
               %(auc)s, %(f1)s, %(precision_score)s, %(recall_score)s, %(brier)s,
               %(n_train)s, %(n_test)s, %(created_at)s, %(updated_at)s)
        """, r)
    conn.commit()
    conn.close()
    logger.info("Done. ablation_runs populated.")

    # Summary
    print("\n=== ABLATION SUMMARY ===")
    from collections import defaultdict
    by_agent: dict = defaultdict(lambda: {"with_graph": [], "graph_ablated": []})
    for r in all_rows:
        by_agent[r["intelligence"]][r["arm"]].append(r["auc"])
    for agent, arms in sorted(by_agent.items()):
        import numpy as np
        wg  = np.mean(arms["with_graph"])   if arms["with_graph"]   else float("nan")
        abl = np.mean(arms["graph_ablated"]) if arms["graph_ablated"] else float("nan")
        print(f"  {agent:10s}  with_graph={wg:.4f}  ablated={abl:.4f}  Δ={wg - abl:+.4f}")


if __name__ == "__main__":
    main()

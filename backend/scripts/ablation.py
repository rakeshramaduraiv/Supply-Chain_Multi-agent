"""
scripts/ablation.py
====================
Run GraphRAG ablation study: with_graph vs graph_ablated arms.

Precondition: processed_master.parquet must exist (run initialization first).

Usage (from supply-chain/ root):
    docker exec amasci-api-dev python /app/scripts/ablation.py

Methodology:
    For each agent and each walk-forward fold, TWO SEPARATE MODELS are trained:

      arm 'with_graph':
          feature_list = FEATURE_CONFIGS[intel_type].features
          (includes GRAPH_CONTEXT_FEATURES)

      arm 'graph_ablated':
          feature_list = [f for f in FEATURE_CONFIGS[intel_type].features
                          if f not in GRAPH_CONTEXT_FEATURES]
          (graph columns REMOVED from the design matrix — never zeroed)

    Everything else is byte-identical between arms:
      - same random_state (seed 42 from hyperparameter dicts)
      - same fold boundaries from WalkForwardValidator
      - same training rows and same test rows
      - same hyperparameters
      - same target

    Zeroing graph columns in a model trained WITH them measures OOD sensitivity,
    not information contribution. This script avoids that error.

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


def _fit_and_score(
    X_tr, y_tr, X_te, y_te,
    feature_list: list[str],
    intel_type,
    trainer,
    fc,
):
    """
    Train a fresh model on X_tr[feature_list] and score on X_te[feature_list].
    Returns metric dict. A new estimator is instantiated per call — never reused.
    """
    from app.ml.utils import ModelTask
    from app.ml.metrics import compute_classification_metrics, compute_regression_metrics

    available = [f for f in feature_list if f in X_tr.columns]
    X_tr_arm = X_tr[available]
    X_te_arm = X_te[available]

    model = trainer._create_model(intel_type)
    model.fit(X_tr_arm, y_tr)

    y_arr = y_te.values
    yp = model.predict(X_te_arm)
    if fc.task == ModelTask.CLASSIFICATION:
        ypr = model.predict_proba(X_te_arm)[:, 1] if hasattr(model, "predict_proba") else None
        return compute_classification_metrics(y_arr, yp, ypr).to_dict(), len(available)
    else:
        return compute_regression_metrics(y_arr, yp).to_dict(), len(available)


def run_ablation_for_agent(df, intel_type, n_splits: int = 5) -> list[dict]:
    """
    Run walk-forward ablation for one agent.
    Returns list of row dicts ready for ablation_runs insert.
    """
    import numpy as np
    from app.ml.utils import (
        FEATURE_CONFIGS, GRAPH_CONTEXT_FEATURES, ModelTask,
        chronological_split, prepare_features,
    )
    from app.ml.validation import WalkForwardValidator
    from app.ml.training import BaseTrainer

    fc      = FEATURE_CONFIGS[intel_type]
    mkey    = "r2" if fc.task == ModelTask.REGRESSION else "roc_auc"
    trainer = BaseTrainer()
    seed    = 42  # matches random_state in all hyperparameter dicts

    full_feature_list    = fc.features
    ablated_feature_list = [f for f in fc.features if f not in GRAPH_CONTEXT_FEATURES]

    # Use the 80% train split only (same as production training)
    train_df, _ = chronological_split(df, train_ratio=0.8)
    X_all, y_all = prepare_features(train_df, fc)

    validator = WalkForwardValidator(n_splits=n_splits)
    splits    = validator.generate_splits(len(X_all))

    run_id = str(uuid.uuid4())
    rows   = []
    now    = datetime.now(timezone.utc)

    fold_deltas: list[float] = []

    for fold_idx, ((tr_s, tr_e), (te_s, te_e)) in enumerate(splits):
        X_tr = X_all.iloc[tr_s:tr_e]
        y_tr = y_all.iloc[tr_s:tr_e]
        X_te = X_all.iloc[te_s:te_e]
        y_te = y_all.iloc[te_s:te_e]

        # with_graph arm — trained on full feature list including graph columns
        m_wg, n_feat_wg = _fit_and_score(
            X_tr, y_tr, X_te, y_te, full_feature_list, intel_type, trainer, fc
        )

        # graph_ablated arm — trained on feature list with graph columns REMOVED
        m_abl, n_feat_abl = _fit_and_score(
            X_tr, y_tr, X_te, y_te, ablated_feature_list, intel_type, trainer, fc
        )

        # Assert the feature count difference equals the number of graph columns removed
        expected_diff = len([f for f in GRAPH_CONTEXT_FEATURES if f in X_tr.columns])
        actual_diff   = n_feat_wg - n_feat_abl
        assert actual_diff == expected_diff, (
            f"Feature count mismatch for {intel_type.value} fold {fold_idx}: "
            f"with_graph has {n_feat_wg} features, ablated has {n_feat_abl} "
            f"(diff={actual_diff}, expected={expected_diff}). "
            f"The ablated feature list was not correctly reduced."
        )

        wg_val  = m_wg.get(mkey, 0.0)
        abl_val = m_abl.get(mkey, 0.0)
        delta   = wg_val - abl_val
        fold_deltas.append(delta)

        logger.info(
            f"  {intel_type.value} fold {fold_idx}: "
            f"with_graph={wg_val:.4f} (n={n_feat_wg})  "
            f"ablated={abl_val:.4f} (n={n_feat_abl})  "
            f"Δ={delta:+.4f}"
        )

        for arm, m, n_feat in [
            ("with_graph",    m_wg,  n_feat_wg),
            ("graph_ablated", m_abl, n_feat_abl),
        ]:
            rows.append({
                "id":              str(uuid.uuid4()),
                "run_id":          run_id,
                "arm":             arm,
                "intelligence":    intel_type.value,
                "window_index":    fold_idx,
                "auc":             m.get(mkey, 0.0),
                "f1":              m.get("f1", 0.0),
                "precision_score": m.get("precision", 0.0),
                "recall_score":    m.get("recall", 0.0),
                "brier":           0.0,
                "n_train":         len(X_tr),
                "n_test":          len(X_te),
                "n_features":      n_feat,
                "seed":            seed,
                "created_at":      now,
                "updated_at":      now,
            })

    # Per-agent fold-level variance report
    import numpy as np
    mean_delta = float(np.mean(fold_deltas))
    std_delta  = float(np.std(fold_deltas))
    logger.info(
        f"  {intel_type.value} fold deltas: {[f'{d:+.4f}' for d in fold_deltas]}"
    )
    logger.info(
        f"  {intel_type.value} mean Δ={mean_delta:+.4f}  std={std_delta:.4f}  "
        f"({'consistent' if std_delta < abs(mean_delta) else 'noisy — delta within fold variance'})"
    )

    return rows


def main():
    from app.core.config import get_settings
    import pandas as pd
    import numpy as np
    from app.ml.utils import IntelligenceType
    from app.feature_engineering import engineer_features

    settings = get_settings()
    parquet  = Path(settings.upload_dir) / "processed_master.parquet"
    if not parquet.exists():
        logger.error(f"processed_master.parquet not found at {parquet}. Run initialization first.")
        sys.exit(1)

    logger.info(f"Loading {parquet} ...")
    df = pd.read_parquet(parquet)
    logger.info(f"Loaded {len(df):,} rows x {len(df.columns)} cols")

    logger.info("Engineering features ...")
    df_eng = engineer_features(df)
    logger.info(f"Engineered: {len(df_eng):,} rows x {len(df_eng.columns)} cols")

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
    logger.info(f"\nPersisting {len(all_rows)} rows to ablation_runs ...")
    conn = _pg()
    cur  = conn.cursor()
    cur.execute("DELETE FROM ablation_runs")
    for r in all_rows:
        cur.execute("""
            INSERT INTO ablation_runs
              (id, run_id, arm, intelligence, window_index,
               auc, f1, precision_score, recall_score, brier,
               n_train, n_test, n_features, seed, created_at, updated_at)
            VALUES
              (%(id)s, %(run_id)s, %(arm)s, %(intelligence)s, %(window_index)s,
               %(auc)s, %(f1)s, %(precision_score)s, %(recall_score)s, %(brier)s,
               %(n_train)s, %(n_test)s, %(n_features)s, %(seed)s,
               %(created_at)s, %(updated_at)s)
        """, r)
    conn.commit()
    conn.close()
    logger.info("Done. ablation_runs populated.")

    # Summary — mean, delta, and fold-level variance side by side
    print("\n=== ABLATION SUMMARY (two-model retrain per arm) ===")
    from collections import defaultdict
    by_agent: dict = defaultdict(lambda: {"with_graph": [], "graph_ablated": []})
    for r in all_rows:
        by_agent[r["intelligence"]][r["arm"]].append(r["auc"])

    for agent, arms in sorted(by_agent.items()):
        wg_vals  = arms["with_graph"]
        abl_vals = arms["graph_ablated"]
        wg   = np.mean(wg_vals)  if wg_vals  else float("nan")
        abl  = np.mean(abl_vals) if abl_vals else float("nan")
        mean_d = wg - abl
        # Paired fold deltas
        fold_d = [w - a for w, a in zip(wg_vals, abl_vals)]
        std_d  = float(np.std(fold_d)) if fold_d else float("nan")
        folds_str = "  ".join(f"{d:+.4f}" for d in fold_d)
        print(
            f"  {agent:10s}  with_graph={wg:.4f}  ablated={abl:.4f}  "
            f"mean_delta={mean_d:+.4f}  fold_std={std_d:.4f}"
        )
        print(f"             fold deltas: [{folds_str}]")
        if std_d > abs(mean_d):
            print(f"             NOTE: fold std ({std_d:.4f}) > |mean delta| ({abs(mean_d):.4f}) "
                  f"— delta is within noise. Not evidence of graph contribution at this scale.")


if __name__ == "__main__":
    main()

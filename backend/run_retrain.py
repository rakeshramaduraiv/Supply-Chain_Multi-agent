"""
Retrain all agents and report AUC + tautology guard results.
Run from: backend/  as  python run_retrain.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import logging
logging.basicConfig(level=logging.WARNING)

import pandas as pd
from app.ml.training import TrainingOrchestrator
from app.ml.utils import TautologicalTargetError

PARQUET = pathlib.Path("data/uploads/processed_master.parquet")

def main():
    if not PARQUET.exists():
        print(f"FAIL: {PARQUET} not found — run initialization first")
        sys.exit(1)

    print(f"Loading {PARQUET} ...")
    df = pd.read_parquet(PARQUET)
    print(f"  {len(df)} rows, {len(df.columns)} columns")

    orch = TrainingOrchestrator()
    results = {}

    for agent in ("demand", "inventory", "supplier", "logistics"):
        from app.ml.utils import IntelligenceType
        itype = IntelligenceType(agent)
        print(f"\n--- {agent.upper()} ---")
        try:
            from app.ml.training import BaseTrainer
            trainer = BaseTrainer(orch.registry)
            r = trainer.train(df, itype, run_walk_forward=False)
            m = r.metrics
            if r.task == "classification":
                auc  = m.get("roc_auc", m.get("auc", "n/a"))
                f1   = m.get("f1_score", m.get("f1", "n/a"))
                acc  = m.get("accuracy", "n/a")
                print(f"  AUC={auc}  F1={f1}  Acc={acc}")
                # Gate check
                if isinstance(auc, float):
                    if auc > 0.98:
                        print(f"  FAIL: AUC {auc:.4f} > 0.98 — tautology guard should have caught this")
                    elif auc > 0.85:
                        print(f"  WARN: AUC {auc:.4f} > 0.85 — possible residual leak, inspect features")
                    elif auc < 0.55:
                        print(f"  WARN: AUC {auc:.4f} < 0.55 — no signal, consider dropping agent")
                    else:
                        print(f"  PASS: AUC in [0.55, 0.85]")
            else:
                r2   = m.get("r2_score", m.get("r2", "n/a"))
                mape = m.get("mape", "n/a")
                rmse = m.get("rmse", "n/a")
                print(f"  R2={r2}  MAPE={mape}  RMSE={rmse}")
            results[agent] = r
        except TautologicalTargetError as e:
            print(f"  TAUTOLOGY GUARD FIRED: {e}")
            results[agent] = None
        except Exception as e:
            print(f"  ERROR: {e}")
            results[agent] = None

    # Agent distinctness check
    print("\n--- AGENT DISTINCTNESS ---")
    import numpy as np
    preds = {}
    for agent, r in results.items():
        if r and r.task == "classification" and r.metrics.get("roc_auc"):
            # We don't have raw preds here — just report AUC spread
            preds[agent] = r.metrics.get("roc_auc", 0)
    for a in preds:
        for b in preds:
            if a < b:
                diff = abs(preds[a] - preds[b])
                print(f"  {a} AUC={preds[a]:.4f}  vs  {b} AUC={preds[b]:.4f}  diff={diff:.4f}")

    print("\nDone.")

if __name__ == "__main__":
    main()

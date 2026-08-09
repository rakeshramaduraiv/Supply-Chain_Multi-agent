"""
Track A gate verification:
1. train_all skips Inventory
2. Supplier & Logistics AUC in [0.55, 0.85]
3. Ablation: amplification ON vs OFF (uses probabilities_raw for both)
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import logging; logging.basicConfig(level=logging.WARNING)

import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score

PARQUET = pathlib.Path("data/uploads/processed_master.parquet")
df = pd.read_parquet(PARQUET)
print(f"Loaded {len(df)} rows\n")

# --- Gate 1: train_all skips Inventory ---
from app.ml.training import TrainingOrchestrator
orch = TrainingOrchestrator()
results = orch.train_all(df, dataset_version="track_a_gate")
print(f"train_all agents: {list(results.keys())}")
assert "inventory" not in results, "FAIL: inventory should be excluded"
print("PASS: inventory excluded from train_all\n")

# --- Gate 2: AUC thresholds ---
for agent in ("supplier", "logistics"):
    auc = results[agent].metrics.get("roc_auc", 0)
    status = "PASS" if 0.55 <= auc <= 0.85 else "FAIL"
    print(f"{status}: {agent} AUC={auc:.4f}")

# --- Gate 3: Ablation — amplification ON vs OFF ---
print("\n--- ABLATION: graph amplification ON vs OFF ---")
from app.ml.prediction import PredictionEngine
from app.ml.utils import IntelligenceType
from app.ml.utils import chronological_split
from app.feature_engineering import engineer_features, engineer_features_on_test

engine = PredictionEngine()
train_raw, test_raw = chronological_split(df, 0.8)
test_eng = engineer_features_on_test(test_raw, train_raw)

# Fake graph context that would trigger amplification
graph_ctx = {
    "avg_supplier_reliability": 0.3,   # < 0.5 -> triggers INVENTORY amp
    "amplified_supplier_count": 2,     # -> triggers SUPPLIER amp
    "upcoming_events": True,           # -> triggers DEMAND amp
}

for agent in (IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS):
    try:
        r_on  = engine.predict(test_eng, agent, graph_context=graph_ctx, apply_amplification=True)
        r_off = engine.predict(test_eng, agent, graph_context=graph_ctx, apply_amplification=False)

        # Both use probabilities_raw for comparison
        raw_on  = np.array(r_on.probabilities_raw)
        raw_off = np.array(r_off.probabilities_raw)

        # raw should be identical (same model, same features)
        raw_identical = np.allclose(raw_on, raw_off, atol=1e-6)

        # final should differ when amplification fires
        final_on  = np.array(r_on.probabilities)
        final_off = np.array(r_off.probabilities)
        final_differ = not np.allclose(final_on, final_off, atol=1e-6)

        amp_info = r_on.graph_amplification
        print(f"\n{agent.value}:")
        print(f"  probabilities_raw identical ON vs OFF: {raw_identical} (expected True)")
        print(f"  probabilities_final differ ON vs OFF:  {final_differ} (expected True if amp fires)")
        print(f"  amplification: {amp_info}")
        if raw_identical:
            print(f"  PASS: raw model output unaffected by amplification flag")
        else:
            print(f"  FAIL: raw output changed — amplification is contaminating model output")
    except Exception as e:
        print(f"  ERROR {agent.value}: {e}")

print("\nDone.")

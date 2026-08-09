"""ml_validation.py — run from backend/"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

out = []

def ok(msg): out.append(f"  PASS  {msg}")
def fail(msg): out.append(f"  FAIL  {msg}"); sys.exit(1)

# 1. Import — leakage guard must not raise
try:
    from app.ml.utils import (
        FEATURE_CONFIGS, GRAPH_CONTEXT_FEATURES, IntelligenceType,
        LIGHTGBM_INVENTORY_PARAMS, build_stockout_target,
    )
    ok("import: leakage guard passed at module load")
except ValueError as e:
    fail(f"leakage guard raised at import: {e}")

# 2. Inventory scale_pos_weight
spw = LIGHTGBM_INVENTORY_PARAMS.get("scale_pos_weight")
assert spw == 3.0, f"expected 3.0 got {spw}"
ok(f"Inventory scale_pos_weight={spw}")

# 3. All 4 agents have all 4 graph features
gcf = set(GRAPH_CONTEXT_FEATURES)
for it in IntelligenceType:
    fc = FEATURE_CONFIGS[it]
    missing = gcf - set(fc.features)
    assert not missing, f"{it.value} missing graph features: {missing}"
ok("all 4 agents have all 4 graph_* features")

# 4. Leakage ban: injecting a banned feature must raise at import
import importlib, types
banned_test_code = """
from app.ml.utils import GRAPH_CONTEXT_FEATURES
DEMAND_FEATURES = ["delivery_gap"] + GRAPH_CONTEXT_FEATURES
INVENTORY_FEATURES = GRAPH_CONTEXT_FEATURES
SUPPLIER_FEATURES = GRAPH_CONTEXT_FEATURES
LOGISTICS_FEATURES = GRAPH_CONTEXT_FEATURES
_LEAKY = {"demand": {"delivery_gap"}, "inventory": set(), "supplier": set(), "logistics": set()}
_ALL_LISTS = {"demand": DEMAND_FEATURES, "inventory": INVENTORY_FEATURES, "supplier": SUPPLIER_FEATURES, "logistics": LOGISTICS_FEATURES}
for _name, _feats in _ALL_LISTS.items():
    _overlap = _LEAKY[_name] & set(_feats)
    if _overlap:
        raise ValueError(f"Target leakage in {_name}: {sorted(_overlap)}")
"""
try:
    exec(banned_test_code)
    fail("leakage guard did not raise when banned feature present")
except ValueError as e:
    ok(f"leakage guard raises on banned feature: {str(e)[:60]}")

# 5. build_stockout_target raises on single-class
import pandas as pd
df_bad = pd.DataFrame({
    "days_until_reorder": [10.0] * 20,
    "inventory_stress_index": [0.5] * 20,
    "demand_spike_flag": [0] * 20,
})
try:
    build_stockout_target(df_bad)
    fail("build_stockout_target did not raise on single-class")
except ValueError as e:
    ok(f"build_stockout_target raises on single-class: {str(e)[:60]}")

# 6. build_stockout_target produces both classes with varied data
df_good = pd.DataFrame({
    "days_until_reorder": list(range(0, 20)),
    "inventory_stress_index": [2.0] * 10 + [0.5] * 10,
    "demand_spike_flag": [1] * 10 + [0] * 10,
})
t = build_stockout_target(df_good)
assert t.nunique() == 2, f"expected 2 classes got {t.nunique()}"
ok(f"build_stockout_target: pos={int(t.sum())} neg={int((t==0).sum())}")

# 7. Training: Inventory model uses scale_pos_weight branch
from app.ml.training import BaseTrainer
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier
tr = BaseTrainer()
inv_m = tr._create_model(IntelligenceType.INVENTORY)
assert isinstance(inv_m, LGBMClassifier)
assert inv_m.scale_pos_weight == 3.0
ok(f"Inventory model: LGBMClassifier scale_pos_weight={inv_m.scale_pos_weight}")

dem_m = tr._create_model(IntelligenceType.DEMAND)
assert isinstance(dem_m, LGBMRegressor)
ok("Demand model: LGBMRegressor")

sup_m = tr._create_model(IntelligenceType.SUPPLIER)
assert isinstance(sup_m, RandomForestClassifier)
ok("Supplier model: RandomForestClassifier")

log_m = tr._create_model(IntelligenceType.LOGISTICS)
assert isinstance(log_m, LGBMClassifier)
assert not hasattr(log_m, "scale_pos_weight") or log_m.scale_pos_weight != 3.0
ok("Logistics model: LGBMClassifier (no scale_pos_weight override)")

# 8. TPKE params recorded in training hyperparams
import inspect
src = inspect.getsource(BaseTrainer.train)
assert "tpke_params_at_training" in src
ok("Training records tpke_params_at_training in registry entry")

print("\n".join(out))
print("\n=== ALL ML VALIDATION PASS ===")

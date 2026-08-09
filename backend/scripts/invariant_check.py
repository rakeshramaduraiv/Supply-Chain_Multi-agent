"""
AMASCI Phase 1 — Correctness Invariant Check
Run: python invariant_check.py  (from backend/)
All assertions must pass before retraining.
"""
import sys

def check(label, fn):
    try:
        fn()
        print(f"  PASS  {label}")
    except Exception as e:
        print(f"  FAIL  {label}: {e}")
        sys.exit(1)

print("=== AMASCI Phase 1 Invariant Check ===")

def c1():
    from app.core.config import get_settings
    s = get_settings()
    assert s.tpke_confidence_threshold == 0.70, f"theta_add={s.tpke_confidence_threshold}"
    assert s.tpke_frequency_threshold == 3,     f"K={s.tpke_frequency_threshold}"
    assert s.tpke_top_k == 3,                   f"top_k={s.tpke_top_k}"
    assert s.tpke_decay_rate == 0.05,           f"delta={s.tpke_decay_rate}"
    assert s.tpke_removal_threshold == 0.10,    f"theta_rem={s.tpke_removal_threshold}"
    assert s.tpke_window_size_days == 30,       f"W={s.tpke_window_size_days}"

check("TPKE params: theta=0.70 K=3 top_k=3 delta=0.05 theta_rem=0.10 W=30", c1)

def c2():
    from app.feature_engineering import ENGINEERED_FEATURES
    gf = [f for f in ENGINEERED_FEATURES if f.startswith("graph_")]
    assert set(gf) == {
        "graph_supplier_reliability", "graph_inventory_stress",
        "graph_has_upcoming_event", "graph_avg_shipping_delay",
    }, f"graph features: {gf}"
    # Spec §3.2 defines the canonical feature list; count must be >= 28
    assert len(ENGINEERED_FEATURES) >= 28, f"feature count={len(ENGINEERED_FEATURES)}"

check("Feature engineering: spec features present, exactly 4 graph_ context features", c2)

def c3():
    from app.ml.utils import FEATURE_CONFIGS, GRAPH_CONTEXT_FEATURES, IntelligenceType
    GCF = set(GRAPH_CONTEXT_FEATURES)
    for it in IntelligenceType:
        fc = FEATURE_CONFIGS[it]
        missing = GCF - set(fc.features)
        assert not missing, f"{it.value} missing graph features: {missing}"
    assert FEATURE_CONFIGS[IntelligenceType.DEMAND].target == "Order Item Quantity"
    assert FEATURE_CONFIGS[IntelligenceType.INVENTORY].target == "stockout_risk_flag"
    assert FEATURE_CONFIGS[IntelligenceType.SUPPLIER].target == "Late_delivery_risk"
    assert FEATURE_CONFIGS[IntelligenceType.LOGISTICS].target == "Late_delivery_risk"

check("ML utils: all 4 agents have 4 graph features, correct targets", c3)

def c4():
    from app.ml.training import BaseTrainer
    from app.ml.utils import IntelligenceType
    from sklearn.ensemble import RandomForestClassifier
    from lightgbm import LGBMRegressor, LGBMClassifier
    t = BaseTrainer()
    assert isinstance(t._create_model(IntelligenceType.SUPPLIER), RandomForestClassifier)
    assert isinstance(t._create_model(IntelligenceType.DEMAND), LGBMRegressor)
    assert isinstance(t._create_model(IntelligenceType.INVENTORY), LGBMClassifier)
    assert isinstance(t._create_model(IntelligenceType.LOGISTICS), LGBMClassifier)

check("Training: Supplier=RF, Demand=LGBMRegressor, Inventory/Logistics=LGBMClassifier", c4)

def c5():
    from app.ml.prediction import DemandPredictor, DemandAgent, PredictionEngine
    import inspect
    assert DemandPredictor is DemandAgent, "DemandPredictor alias broken"
    sig = inspect.signature(PredictionEngine.predict)
    assert "graph_context" in sig.parameters, "predict() missing graph_context param"

check("Prediction: DemandPredictor alias, predict() has graph_context param", c5)

def c6():
    from app.graphrag.graph_context import GraphContextService
    ctx = GraphContextService._default_agent_context("Electronics", "West")
    assert ctx.get("_cold_start") is True, f"_cold_start={ctx.get('_cold_start')}"
    required = ["avg_supplier_reliability", "inventory_stress", "avg_shipping_delay",
                "upcoming_events", "holiday_risk_events", "amplified_supplier_count"]
    for k in required:
        assert k in ctx, f"missing key: {k}"

check("GraphRAG: _default_agent_context has _cold_start=True and all required keys", c6)

def c7():
    from app.services.domain.forecast_service import ForecastService
    import inspect
    assert hasattr(ForecastService, "run_graph_aware_forecast")
    src = inspect.getsource(ForecastService.run_graph_aware_forecast)
    assert "get_agent_context" in src
    assert "graph_context" in src

check("ForecastService: run_graph_aware_forecast wired to GraphRAG", c7)

print()
print("=== ALL INVARIANTS PASS ===")

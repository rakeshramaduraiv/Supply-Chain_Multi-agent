"""
tests/critical/test_inventory_excluded.py
==========================================
Asserts the Inventory agent is permanently excluded.
DataCo contains no independent inventory signal (CV AUC 0.479).
"""
import json
import pathlib
import pytest

MODELS_DIR = pathlib.Path(__file__).parents[2] / "data" / "models"
REGISTRY   = MODELS_DIR / "registry.json"


def test_no_inventory_joblib():
    inv_dir = MODELS_DIR / "inventory"
    files = list(inv_dir.glob("*.joblib")) if inv_dir.exists() else []
    assert files == [], f"Inventory .joblib files must not exist: {files}"


def test_registry_has_no_inventory():
    if not REGISTRY.exists():
        pytest.skip("registry.json not yet created (pre-initialization)")
    d = json.loads(REGISTRY.read_text())
    assert "inventory" not in d, (
        f"registry.json must not contain 'inventory' key. Found keys: {list(d.keys())}"
    )


def test_registry_has_exactly_three_agents():
    if not REGISTRY.exists():
        pytest.skip("registry.json not yet created (pre-initialization)")
    d = json.loads(REGISTRY.read_text())
    assert set(d.keys()) == {"demand", "supplier", "logistics"}, (
        f"Registry must have exactly demand/supplier/logistics. Got: {set(d.keys())}"
    )


def test_training_orchestrator_has_no_train_inventory():
    from app.ml.training import TrainingOrchestrator
    assert not hasattr(TrainingOrchestrator, "train_inventory"), (
        "TrainingOrchestrator must not have train_inventory method"
    )


def test_inventory_absent_from_feature_configs():
    from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
    assert IntelligenceType.INVENTORY not in FEATURE_CONFIGS, (
        "IntelligenceType.INVENTORY must not appear in FEATURE_CONFIGS"
    )


def test_orchestrator_weights_exclude_inventory():
    from app.ml.orchestrator import DEFAULT_WEIGHTS
    assert "inventory" not in DEFAULT_WEIGHTS, (
        f"DEFAULT_WEIGHTS must not contain 'inventory'. Got: {DEFAULT_WEIGHTS}"
    )
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.001, (
        f"DEFAULT_WEIGHTS must sum to 1.0. Got: {sum(DEFAULT_WEIGHTS.values())}"
    )

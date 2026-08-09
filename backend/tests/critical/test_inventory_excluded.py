"""
tests/critical/test_inventory_excluded.py
==========================================
Asserts the Inventory agent is permanently excluded.

Rationale: DataCo's synthetic stockout_risk_flag target is algebraically
derived from rolling demand features (qty_roll_7, qty_roll_30, demand_momentum).
A depth-3 decision tree achieves train AUC 0.988; cross-validated AUC with
non-tautological features is 0.479. No learnable signal exists.
"""

import json
import pathlib
import sys

import pytest

REGISTRY_PATH = pathlib.Path("data/models/registry.json")
MODELS_DIR    = pathlib.Path("data/models")

# ── Registry ──────────────────────────────────────────────────────────────────

def test_inventory_not_in_registry():
    assert REGISTRY_PATH.exists(), f"Registry not found at {REGISTRY_PATH}"
    registry = json.loads(REGISTRY_PATH.read_text())
    assert "inventory" not in registry, (
        f"'inventory' key found in registry.json — "
        f"delete it with purge_inventory_registry.py"
    )


# ── Filesystem ────────────────────────────────────────────────────────────────

def test_no_inventory_joblib():
    if not MODELS_DIR.exists():
        pytest.skip(f"{MODELS_DIR} does not exist")
    matches = list(MODELS_DIR.glob("inventory_*.joblib"))
    assert matches == [], (
        f"Found inventory joblib files that must be deleted: {matches}"
    )


# ── Training code ─────────────────────────────────────────────────────────────

def test_training_orchestrator_has_no_train_inventory():
    # Add backend to path so imports work when run from repo root
    backend = pathlib.Path(__file__).parent.parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from app.ml.training import TrainingOrchestrator
    orchestrator = TrainingOrchestrator.__new__(TrainingOrchestrator)
    assert not hasattr(orchestrator, "train_inventory"), (
        "TrainingOrchestrator still has train_inventory — delete the method"
    )


def test_training_orchestrator_has_no_inventory_trainer_attribute():
    backend = pathlib.Path(__file__).parent.parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from app.ml.training import TrainingOrchestrator
    orchestrator = TrainingOrchestrator.__new__(TrainingOrchestrator)
    assert not hasattr(orchestrator, "inventory_trainer"), (
        "TrainingOrchestrator still has inventory_trainer attribute"
    )


def test_no_inventory_trainer_class():
    backend = pathlib.Path(__file__).parent.parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    import app.ml.training as training_module
    assert not hasattr(training_module, "InventoryTrainer"), (
        "InventoryTrainer class still exists in app.ml.training"
    )


# ── Feature config ────────────────────────────────────────────────────────────

def test_inventory_not_in_feature_configs():
    backend = pathlib.Path(__file__).parent.parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from app.ml.utils import FEATURE_CONFIGS, IntelligenceType
    assert IntelligenceType.INVENTORY not in FEATURE_CONFIGS, (
        "IntelligenceType.INVENTORY still has an entry in FEATURE_CONFIGS"
    )


def test_inventory_symbols_absent_from_utils():
    backend = pathlib.Path(__file__).parent.parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    import app.ml.utils as utils_module
    for name in ("INVENTORY_FEATURES", "INVENTORY_TARGET",
                 "LIGHTGBM_INVENTORY_PARAMS", "build_stockout_target"):
        assert not hasattr(utils_module, name), (
            f"{name} still exported from app.ml.utils — delete it"
        )

"""
Unit tests for Model Registry module.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from lightgbm import LGBMClassifier

from app.ml.registry import ModelRegistry, ModelVersion
from app.ml.utils import IntelligenceType, ModelTask


@pytest.fixture
def temp_registry():
    """Create a temporary model registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ModelRegistry(base_dir=Path(tmpdir))


def _train_dummy_model():
    """Train a minimal model for testing."""
    X = np.random.rand(100, 5)
    y = np.random.randint(0, 2, 100)
    model = LGBMClassifier(n_estimators=5, max_depth=2, verbose=-1, random_state=42)
    model.fit(X, y)
    return model


class TestModelRegistry:
    """Tests for model registry."""

    def test_save_model(self, temp_registry):
        model = _train_dummy_model()
        version = temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.INVENTORY,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1", "f2", "f3", "f4", "f5"],
            metrics={"accuracy": 0.85, "f1": 0.82},
            training_duration_ms=1500.0,
            n_training_samples=100,
        )

        assert version.version_id != ""
        assert version.intelligence_type == "inventory"
        assert version.is_active is True
        assert version.n_training_samples == 100

    def test_load_model(self, temp_registry):
        model = _train_dummy_model()
        version = temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.INVENTORY,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1", "f2"],
            metrics={"accuracy": 0.9},
            training_duration_ms=1000.0,
        )

        loaded = temp_registry.load_model(IntelligenceType.INVENTORY)
        assert loaded is not None
        # Verify it can predict
        preds = loaded.predict(np.random.rand(5, 5))
        assert len(preds) == 5

    def test_load_specific_version(self, temp_registry):
        model1 = _train_dummy_model()
        v1 = temp_registry.save_model(
            model=model1,
            intelligence_type=IntelligenceType.SUPPLIER,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1"],
            metrics={"accuracy": 0.8},
            training_duration_ms=500.0,
        )

        model2 = _train_dummy_model()
        v2 = temp_registry.save_model(
            model=model2,
            intelligence_type=IntelligenceType.SUPPLIER,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1", "f2"],
            metrics={"accuracy": 0.85},
            training_duration_ms=600.0,
        )

        # Latest should be v2
        latest = temp_registry.get_latest_version(IntelligenceType.SUPPLIER)
        assert latest.version_id == v2.version_id

        # Can load v1 specifically
        loaded = temp_registry.load_model(IntelligenceType.SUPPLIER, v1.version_id)
        assert loaded is not None

    def test_list_versions(self, temp_registry):
        model = _train_dummy_model()
        temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.LOGISTICS,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1"],
            metrics={},
            training_duration_ms=100.0,
        )
        temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.LOGISTICS,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1"],
            metrics={},
            training_duration_ms=100.0,
        )

        versions = temp_registry.list_versions(IntelligenceType.LOGISTICS)
        assert len(versions) == 2

    def test_rollback(self, temp_registry):
        model = _train_dummy_model()
        v1 = temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.DEMAND,
            task=ModelTask.REGRESSION,
            features_used=["f1"],
            metrics={"r2": 0.7},
            training_duration_ms=100.0,
        )
        v2 = temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.DEMAND,
            task=ModelTask.REGRESSION,
            features_used=["f1"],
            metrics={"r2": 0.75},
            training_duration_ms=100.0,
        )

        # v2 is active
        latest = temp_registry.get_latest_version(IntelligenceType.DEMAND)
        assert latest.version_id == v2.version_id

        # Rollback to v1
        rolled = temp_registry.rollback(IntelligenceType.DEMAND, v1.version_id)
        assert rolled.version_id == v1.version_id
        assert rolled.is_active is True

        # Now v1 is active
        latest = temp_registry.get_latest_version(IntelligenceType.DEMAND)
        assert latest.version_id == v1.version_id

    def test_delete_version(self, temp_registry):
        model = _train_dummy_model()
        v = temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.INVENTORY,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1"],
            metrics={},
            training_duration_ms=100.0,
        )

        deleted = temp_registry.delete_version(IntelligenceType.INVENTORY, v.version_id)
        assert deleted is True

        versions = temp_registry.list_versions(IntelligenceType.INVENTORY)
        assert len(versions) == 0

    def test_load_nonexistent_raises(self, temp_registry):
        with pytest.raises(FileNotFoundError):
            temp_registry.load_model(IntelligenceType.DEMAND)

    def test_list_all_models(self, temp_registry):
        model = _train_dummy_model()
        temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.DEMAND,
            task=ModelTask.REGRESSION,
            features_used=["f1"],
            metrics={},
            training_duration_ms=100.0,
        )
        temp_registry.save_model(
            model=model,
            intelligence_type=IntelligenceType.INVENTORY,
            task=ModelTask.CLASSIFICATION,
            features_used=["f1"],
            metrics={},
            training_duration_ms=100.0,
        )

        all_models = temp_registry.list_all_models()
        assert "demand" in all_models
        assert "inventory" in all_models

    def test_registry_persistence(self):
        """Test that registry survives reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            # Save with first instance
            reg1 = ModelRegistry(base_dir=base_dir)
            model = _train_dummy_model()
            v = reg1.save_model(
                model=model,
                intelligence_type=IntelligenceType.SUPPLIER,
                task=ModelTask.CLASSIFICATION,
                features_used=["f1"],
                metrics={"accuracy": 0.9},
                training_duration_ms=100.0,
            )

            # Load with new instance
            reg2 = ModelRegistry(base_dir=base_dir)
            versions = reg2.list_versions(IntelligenceType.SUPPLIER)
            assert len(versions) == 1
            assert versions[0].version_id == v.version_id

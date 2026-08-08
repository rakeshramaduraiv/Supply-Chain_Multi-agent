"""
AMASCI Model Registry
======================
Enterprise model versioning, persistence, and lifecycle management.
"""

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from app.core.config import get_settings
from app.ml.utils import IntelligenceType, ModelTask

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Metadata for a registered model version."""
    version_id: str
    intelligence_type: str
    task: str
    model_path: str
    created_at: str
    training_duration_ms: float
    features_used: list[str]
    metrics: dict[str, Any]
    dataset_version: str = ""
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    n_training_samples: int = 0
    is_active: bool = True
    description: str = ""
    graph_enriched: bool = False  # True only when Neo4j enrichment actually ran

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelRegistry:
    """
    Enterprise model registry for versioning and lifecycle management.

    Supports:
    - Save/load models with joblib
    - Version tracking with metadata
    - Rollback to previous versions
    - Active model resolution
    """

    def __init__(self, base_dir: Path | None = None):
        settings = get_settings()
        self._base_dir = base_dir or settings.model_path
        self._registry_file = self._base_dir / "registry.json"
        self._versions: dict[str, list[ModelVersion]] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from disk."""
        if self._registry_file.exists():
            try:
                data = json.loads(self._registry_file.read_text())
                for intel_type, versions in data.items():
                    self._versions[intel_type] = [
                        ModelVersion(**v) for v in versions
                    ]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Registry file corrupted, starting fresh: {e}")
                self._versions = {}
        else:
            self._versions = {}

    def _save_registry(self) -> None:
        """Persist registry to disk."""
        data = {
            k: [v.to_dict() for v in versions]
            for k, versions in self._versions.items()
        }
        self._registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._registry_file.write_text(json.dumps(data, indent=2, default=str))

    def _generate_version_id(self, intelligence_type: IntelligenceType) -> str:
        """Generate unique version ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        hash_suffix = hashlib.md5(f"{intelligence_type.value}_{time.time()}".encode()).hexdigest()[:6]
        return f"{intelligence_type.value}_v_{timestamp}_{hash_suffix}"

    def save_model(
        self,
        model: Any,
        intelligence_type: IntelligenceType,
        task: ModelTask,
        features_used: list[str],
        metrics: dict[str, Any],
        training_duration_ms: float,
        hyperparameters: dict[str, Any] | None = None,
        dataset_version: str = "",
        n_training_samples: int = 0,
        description: str = "",
        graph_enriched: bool = False,
    ) -> ModelVersion:
        """
        Save a trained model to the registry.

        Returns the created ModelVersion metadata.
        """
        version_id = self._generate_version_id(intelligence_type)
        model_dir = self._base_dir / intelligence_type.value
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / f"{version_id}.joblib"
        joblib.dump(model, model_path)

        version = ModelVersion(
            version_id=version_id,
            intelligence_type=intelligence_type.value,
            task=task.value,
            model_path=str(model_path),
            created_at=datetime.now(timezone.utc).isoformat(),
            training_duration_ms=training_duration_ms,
            features_used=features_used,
            metrics=metrics,
            dataset_version=dataset_version,
            hyperparameters=hyperparameters or {},
            n_training_samples=n_training_samples,
            is_active=True,
            description=description,
            graph_enriched=graph_enriched,
        )

        # Deactivate previous versions
        key = intelligence_type.value
        if key not in self._versions:
            self._versions[key] = []
        for v in self._versions[key]:
            v.is_active = False

        self._versions[key].append(version)

        # Prune to latest 3 versions — delete excess .joblib files from disk
        _KEEP = 3
        all_versions = self._versions[key]
        if len(all_versions) > _KEEP:
            to_prune = all_versions[:-_KEEP]
            for old in to_prune:
                old_path = Path(old.model_path)
                if old_path.exists():
                    try:
                        old_path.unlink()
                    except OSError as prune_err:
                        logger.warning(f"Could not delete old model file {old_path}: {prune_err}")
            self._versions[key] = all_versions[-_KEEP:]

        self._save_registry()

        logger.info(f"Model saved: {version_id} ({intelligence_type.value})")
        return version

    def load_model(self, intelligence_type: IntelligenceType, version_id: str | None = None) -> Any:
        """
        Load a model from registry.

        If version_id is None, loads the latest active version.
        """
        version = self.get_version(intelligence_type, version_id)
        if version is None:
            raise FileNotFoundError(
                f"No model found for {intelligence_type.value}"
                + (f" version {version_id}" if version_id else "")
            )

        model_path = Path(version.model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        model = joblib.load(model_path)
        logger.info(f"Model loaded: {version.version_id}")
        return model

    def get_version(
        self, intelligence_type: IntelligenceType, version_id: str | None = None
    ) -> ModelVersion | None:
        """Get a specific version or the latest active version."""
        key = intelligence_type.value
        versions = self._versions.get(key, [])
        if not versions:
            return None

        if version_id:
            for v in versions:
                if v.version_id == version_id:
                    return v
            return None

        # Return latest active, or just latest
        active = [v for v in versions if v.is_active]
        return active[-1] if active else versions[-1]

    def get_latest_version(self, intelligence_type: IntelligenceType) -> ModelVersion | None:
        """Get the latest model version."""
        return self.get_version(intelligence_type)

    def list_versions(self, intelligence_type: IntelligenceType) -> list[ModelVersion]:
        """List all versions for an intelligence type."""
        return self._versions.get(intelligence_type.value, [])

    def list_all_models(self) -> dict[str, list[dict[str, Any]]]:
        """List all registered models across all intelligence types."""
        return {
            k: [v.to_dict() for v in versions]
            for k, versions in self._versions.items()
        }

    def rollback(self, intelligence_type: IntelligenceType, version_id: str) -> ModelVersion | None:
        """Rollback to a specific version (make it active)."""
        key = intelligence_type.value
        versions = self._versions.get(key, [])

        target = None
        for v in versions:
            if v.version_id == version_id:
                target = v
            v.is_active = False

        if target:
            target.is_active = True
            self._save_registry()
            logger.info(f"Rolled back to: {version_id}")

        return target

    def delete_version(self, intelligence_type: IntelligenceType, version_id: str) -> bool:
        """Delete a model version from registry and disk."""
        key = intelligence_type.value
        versions = self._versions.get(key, [])

        for i, v in enumerate(versions):
            if v.version_id == version_id:
                model_path = Path(v.model_path)
                if model_path.exists():
                    model_path.unlink()
                versions.pop(i)
                self._save_registry()
                logger.info(f"Deleted model version: {version_id}")
                return True

        return False

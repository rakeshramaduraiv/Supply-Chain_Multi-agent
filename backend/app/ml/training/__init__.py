"""
AMASCI Training Module
========================
Model training pipelines for all intelligence services.

Services:
- DemandTrainer: LightGBM Regressor for 7-day demand forecast
- InventoryTrainer: LightGBM Classifier for stockout prediction
- SupplierTrainer: RandomForest Classifier for late delivery risk
- LogisticsTrainer: LightGBM Classifier for route delay risk
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier

from app.ml.confidence import (
    compute_classification_confidence,
    compute_regression_confidence,
)
from app.ml.feature_importance import compute_feature_importance
from app.ml.metrics import (
    compute_classification_metrics,
    compute_regression_metrics,
)
from app.ml.registry import ModelRegistry
from app.ml.utils import (
    FEATURE_CONFIGS,
    LIGHTGBM_CLASSIFIER_PARAMS,
    LIGHTGBM_REGRESSOR_PARAMS,
    RANDOM_FOREST_PARAMS,
    IntelligenceType,
    ModelTask,
    chronological_split,
    prepare_features,
)
from app.ml.validation import WalkForwardValidator

logger = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """Result of a model training run."""
    intelligence_type: str
    version_id: str
    task: str
    metrics: dict[str, Any]
    feature_importance: dict[str, Any]
    walk_forward_result: dict[str, Any] | None = None
    confidence_summary: dict[str, Any] = field(default_factory=dict)
    training_duration_ms: float = 0.0
    n_training_samples: int = 0
    n_test_samples: int = 0
    features_used: list[str] = field(default_factory=list)
    hyperparameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intelligence_type": self.intelligence_type,
            "version_id": self.version_id,
            "task": self.task,
            "metrics": self.metrics,
            "feature_importance": self.feature_importance,
            "walk_forward_result": self.walk_forward_result,
            "confidence_summary": self.confidence_summary,
            "training_duration_ms": round(self.training_duration_ms, 2),
            "n_training_samples": self.n_training_samples,
            "n_test_samples": self.n_test_samples,
            "features_used": self.features_used,
            "hyperparameters": self.hyperparameters,
        }


class BaseTrainer:
    """Base trainer with shared training logic."""

    def __init__(self, registry: ModelRegistry | None = None):
        self.registry = registry or ModelRegistry()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _create_model(self, intelligence_type: IntelligenceType) -> Any:
        """Create a fresh model instance based on intelligence type."""
        if intelligence_type == IntelligenceType.DEMAND:
            return LGBMRegressor(**LIGHTGBM_REGRESSOR_PARAMS)
        elif intelligence_type == IntelligenceType.SUPPLIER:
            return RandomForestClassifier(**RANDOM_FOREST_PARAMS)
        else:
            return LGBMClassifier(**LIGHTGBM_CLASSIFIER_PARAMS)

    def _get_hyperparameters(self, intelligence_type: IntelligenceType) -> dict[str, Any]:
        """Get hyperparameters for the intelligence type."""
        if intelligence_type == IntelligenceType.DEMAND:
            return LIGHTGBM_REGRESSOR_PARAMS.copy()
        elif intelligence_type == IntelligenceType.SUPPLIER:
            return RANDOM_FOREST_PARAMS.copy()
        else:
            return LIGHTGBM_CLASSIFIER_PARAMS.copy()

    def train(
        self,
        df: pd.DataFrame,
        intelligence_type: IntelligenceType,
        run_walk_forward: bool = True,
        dataset_version: str = "",
    ) -> TrainingResult:
        """
        Execute full training pipeline.

        Steps:
        1. Feature preparation
        2. Chronological split
        3. Walk-forward validation (optional)
        4. Final model training
        5. Evaluation on holdout
        6. Feature importance computation
        7. Confidence estimation
        8. Model persistence via registry
        """
        start_time = time.perf_counter()
        feature_config = FEATURE_CONFIGS[intelligence_type]

        self.logger.info(f"Training {intelligence_type.value} model...")

        # Prepare features
        X, y = prepare_features(df, feature_config)
        train_df, test_df = chronological_split(df, train_ratio=0.8)

        X_train, y_train = prepare_features(train_df, feature_config)
        X_test, y_test = prepare_features(test_df, feature_config)

        features_used = X_train.columns.tolist()
        hyperparams = self._get_hyperparameters(intelligence_type)

        # Walk-forward validation
        wf_result = None
        if run_walk_forward and len(X) > 500:
            validator = WalkForwardValidator(n_splits=5)
            wf_result_obj = validator.validate(
                df=train_df,
                feature_config=feature_config,
                model_factory=lambda: self._create_model(intelligence_type),
            )
            wf_result = wf_result_obj.to_dict()

        # Train final model on full training set
        model = self._create_model(intelligence_type)
        model.fit(X_train, y_train)

        # Evaluate on holdout
        y_pred = model.predict(X_test)

        if feature_config.task == ModelTask.CLASSIFICATION:
            y_prob = None
            if hasattr(model, "predict_proba"):
                y_prob = model.predict_proba(X_test)[:, 1]
            metrics_obj = compute_classification_metrics(y_test.values, y_pred, y_prob)
            metrics = metrics_obj.to_dict()

            # Confidence
            if y_prob is not None:
                conf = compute_classification_confidence(y_prob, y_test.values)
                confidence_summary = conf.to_dict()
            else:
                confidence_summary = {}
        else:
            metrics_obj = compute_regression_metrics(y_test.values, y_pred)
            metrics = metrics_obj.to_dict()
            conf = compute_regression_confidence(y_pred, y_test.values)
            confidence_summary = conf.to_dict()

        # Feature importance
        fi_result = compute_feature_importance(model, features_used)
        feature_importance = fi_result.to_dict()

        training_duration_ms = (time.perf_counter() - start_time) * 1000

        # Save to registry
        version = self.registry.save_model(
            model=model,
            intelligence_type=intelligence_type,
            task=feature_config.task,
            features_used=features_used,
            metrics=metrics,
            training_duration_ms=training_duration_ms,
            hyperparameters=hyperparams,
            dataset_version=dataset_version,
            n_training_samples=len(X_train),
        )

        result = TrainingResult(
            intelligence_type=intelligence_type.value,
            version_id=version.version_id,
            task=feature_config.task.value,
            metrics=metrics,
            feature_importance=feature_importance,
            walk_forward_result=wf_result,
            confidence_summary=confidence_summary,
            training_duration_ms=training_duration_ms,
            n_training_samples=len(X_train),
            n_test_samples=len(X_test),
            features_used=features_used,
            hyperparameters=hyperparams,
        )

        self.logger.info(
            f"Training complete: {intelligence_type.value} "
            f"v={version.version_id} duration={training_duration_ms:.1f}ms"
        )
        return result


class DemandTrainer(BaseTrainer):
    """Trainer for Demand Intelligence (LightGBM Regressor)."""

    def train_demand(self, df: pd.DataFrame, dataset_version: str = "") -> TrainingResult:
        return self.train(df, IntelligenceType.DEMAND, dataset_version=dataset_version)


class InventoryTrainer(BaseTrainer):
    """Trainer for Inventory Intelligence (LightGBM Classifier)."""

    def train_inventory(self, df: pd.DataFrame, dataset_version: str = "") -> TrainingResult:
        return self.train(df, IntelligenceType.INVENTORY, dataset_version=dataset_version)


class SupplierTrainer(BaseTrainer):
    """Trainer for Supplier Intelligence (RandomForest Classifier)."""

    def train_supplier(self, df: pd.DataFrame, dataset_version: str = "") -> TrainingResult:
        return self.train(df, IntelligenceType.SUPPLIER, dataset_version=dataset_version)


class LogisticsTrainer(BaseTrainer):
    """Trainer for Logistics Intelligence (LightGBM Classifier)."""

    def train_logistics(self, df: pd.DataFrame, dataset_version: str = "") -> TrainingResult:
        return self.train(df, IntelligenceType.LOGISTICS, dataset_version=dataset_version)


class TrainingOrchestrator:
    """Orchestrates training across all intelligence services."""

    def __init__(self, registry: ModelRegistry | None = None):
        self.registry = registry or ModelRegistry()
        self.demand_trainer = DemandTrainer(self.registry)
        self.inventory_trainer = InventoryTrainer(self.registry)
        self.supplier_trainer = SupplierTrainer(self.registry)
        self.logistics_trainer = LogisticsTrainer(self.registry)

    def train_all(
        self, df: pd.DataFrame, dataset_version: str = ""
    ) -> dict[str, TrainingResult]:
        """Train all intelligence models on the same dataset."""
        results = {}

        results["demand"] = self.demand_trainer.train_demand(df, dataset_version)
        results["inventory"] = self.inventory_trainer.train_inventory(df, dataset_version)
        results["supplier"] = self.supplier_trainer.train_supplier(df, dataset_version)
        results["logistics"] = self.logistics_trainer.train_logistics(df, dataset_version)

        logger.info(f"All models trained: {list(results.keys())}")
        return results

    def train_single(
        self,
        df: pd.DataFrame,
        intelligence_type: IntelligenceType,
        dataset_version: str = "",
    ) -> TrainingResult:
        """Train a single intelligence model."""
        trainer = BaseTrainer(self.registry)
        return trainer.train(df, intelligence_type, dataset_version=dataset_version)

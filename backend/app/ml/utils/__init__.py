"""
AMASCI ML Utilities
====================
Shared constants, feature definitions, and helper functions for ML pipeline.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class IntelligenceType(str, Enum):
    """Types of intelligence services."""
    DEMAND = "demand"
    INVENTORY = "inventory"
    SUPPLIER = "supplier"
    LOGISTICS = "logistics"


class ModelTask(str, Enum):
    """ML task types."""
    REGRESSION = "regression"
    CLASSIFICATION = "classification"


@dataclass
class FeatureConfig:
    """Feature configuration for an intelligence service."""
    features: list[str]
    target: str
    task: ModelTask
    categorical_features: list[str] = field(default_factory=list)


# --- Feature Definitions per Intelligence Service ---

DEMAND_FEATURES = [
    "order_month", "order_day_of_week", "order_week_of_year", "order_quarter",
    "order_is_weekend", "Sales", "Order Profit Per Order",
    "Product Price", "Order Item Discount", "Days for shipping (real)",
    "Days for shipment (scheduled)", "delivery_duration_days",
]

DEMAND_TARGET = "Order Item Quantity"

INVENTORY_FEATURES = [
    "order_month", "order_day_of_week", "order_quarter", "order_is_weekend",
    "Order Item Quantity", "Sales", "Product Price", "Order Item Discount",
    "Days for shipping (real)", "Days for shipment (scheduled)",
    "delivery_duration_days", "Order Profit Per Order",
]

INVENTORY_TARGET = "Late_delivery_risk"

SUPPLIER_FEATURES = [
    "Days for shipping (real)", "Days for shipment (scheduled)",
    "order_month", "order_quarter", "order_day_of_week",
    "Order Item Quantity", "Sales", "Product Price",
    "Order Item Discount", "Order Profit Per Order",
    "delivery_duration_days", "order_is_weekend",
]

SUPPLIER_TARGET = "Late_delivery_risk"

LOGISTICS_FEATURES = [
    "Days for shipping (real)", "Days for shipment (scheduled)",
    "delivery_duration_days", "order_month", "order_day_of_week",
    "order_quarter", "order_is_weekend", "Order Item Quantity",
    "Sales", "Product Price", "Order Item Discount",
    "Order Profit Per Order",
]

LOGISTICS_TARGET = "Late_delivery_risk"


FEATURE_CONFIGS: dict[IntelligenceType, FeatureConfig] = {
    IntelligenceType.DEMAND: FeatureConfig(
        features=DEMAND_FEATURES,
        target=DEMAND_TARGET,
        task=ModelTask.REGRESSION,
    ),
    IntelligenceType.INVENTORY: FeatureConfig(
        features=INVENTORY_FEATURES,
        target=INVENTORY_TARGET,
        task=ModelTask.CLASSIFICATION,
    ),
    IntelligenceType.SUPPLIER: FeatureConfig(
        features=SUPPLIER_FEATURES,
        target=SUPPLIER_TARGET,
        task=ModelTask.CLASSIFICATION,
    ),
    IntelligenceType.LOGISTICS: FeatureConfig(
        features=LOGISTICS_FEATURES,
        target=LOGISTICS_TARGET,
        task=ModelTask.CLASSIFICATION,
    ),
}


# --- Default Hyperparameters ---

LIGHTGBM_CLASSIFIER_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 7,
    "num_leaves": 63,
    "min_child_samples": 50,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}

LIGHTGBM_REGRESSOR_PARAMS = {
    "objective": "regression",
    "metric": "rmse",
    "boosting_type": "gbdt",
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 7,
    "num_leaves": 63,
    "min_child_samples": 50,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}

RANDOM_FOREST_PARAMS = {
    "n_estimators": 300,
    "max_depth": 12,
    "min_samples_split": 10,
    "min_samples_leaf": 5,
    "max_features": "sqrt",
    "random_state": 42,
    "n_jobs": -1,
}


def prepare_features(
    df: pd.DataFrame,
    feature_config: FeatureConfig,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Prepare feature matrix X and target vector y from dataframe.

    Returns only rows where all features and target are non-null.
    """
    available_features = [f for f in feature_config.features if f in df.columns and f != feature_config.target]
    if not available_features:
        raise ValueError(f"No configured features found in dataframe. Expected: {feature_config.features}")

    if feature_config.target not in df.columns:
        raise ValueError(f"Target column '{feature_config.target}' not found in dataframe")

    subset = df[available_features + [feature_config.target]].dropna()
    X = subset[available_features]
    y = subset[feature_config.target]

    logger.info(f"Prepared features: {len(available_features)} features, {len(X)} samples")
    return X, y


def chronological_split(
    df: pd.DataFrame,
    train_ratio: float = 0.8,
    date_column: str = "order date (DateOrders)",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split dataframe chronologically (no shuffling).

    Assumes df is already sorted by date.
    """
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    logger.info(f"Chronological split: train={len(train_df)}, test={len(test_df)}")
    return train_df, test_df

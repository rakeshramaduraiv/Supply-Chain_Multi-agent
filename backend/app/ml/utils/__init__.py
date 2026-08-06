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
# Each agent uses DOMAIN-SPECIFIC engineered features + graph context.
# The 4 graph_* features are defaulted at training and injected live
# from Neo4j via GraphRAG at prediction time.

GRAPH_CONTEXT_FEATURES = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_has_upcoming_event",
    "graph_avg_shipping_delay",
]

# ── DEMAND AGENT ──────────────────────────────────────────────
# Predicts: next-period demand quantity (REGRESSION)
DEMAND_FEATURES = [
    "rolling_7d_demand", "rolling_14d_demand", "rolling_30d_demand",
    "demand_volatility", "demand_spike_flag", "demand_trend_slope",
    "demand_momentum", "demand_intensity", "quantity_zscore",
    "seasonality_index", "category_demand_rank",
    "demand_lag_1m", "demand_lag_3m",
    "Product Price", "Order Item Discount", "discount_impact",
    "price_quantity_interaction",
    "order_month", "order_quarter", "order_week_of_year", "order_is_weekend",
] + GRAPH_CONTEXT_FEATURES

DEMAND_TARGET = "Order Item Quantity"


# ── INVENTORY AGENT ───────────────────────────────────────────
# Predicts: stockout risk (CLASSIFICATION)
INVENTORY_FEATURES = [
    "inventory_stress_index", "days_until_reorder", "stock_coverage_ratio",
    "rolling_7d_demand", "rolling_14d_demand", "rolling_30d_demand",
    "demand_volatility", "demand_spike_flag", "demand_momentum",
    "supplier_reliability_score", "supplier_delay_rate",
    "delivery_duration_days", "delivery_gap",
    "order_month", "order_quarter",
] + GRAPH_CONTEXT_FEATURES

INVENTORY_TARGET = "stockout_risk_flag"


# ── SUPPLIER AGENT ────────────────────────────────────────────
# Predicts: late delivery risk (CLASSIFICATION) — PRIMARY ML OBJECTIVE
SUPPLIER_FEATURES = [
    "supplier_reliability_score", "supplier_delay_rate",
    "supplier_risk_index", "supplier_volume",
    "delivery_duration_days", "shipping_delay_ratio",
    "is_delayed", "delivery_gap",
    "Days for shipping (real)", "Days for shipment (scheduled)",
    "supplier_delay_lag_1m", "delay_rolling_mean_3m",
    "demand_spike_flag", "demand_volatility",
    "order_month", "order_quarter",
] + GRAPH_CONTEXT_FEATURES

SUPPLIER_TARGET = "Late_delivery_risk"


# ── LOGISTICS AGENT ───────────────────────────────────────────
# Predicts: route-level delivery delay risk (CLASSIFICATION)
LOGISTICS_FEATURES = [
    "delivery_duration_days", "shipping_delay_ratio", "is_delayed",
    "delivery_gap", "delay_rolling_mean_3m",
    "Days for shipping (real)", "Days for shipment (scheduled)",
    "order_value_log", "revenue_per_unit", "Order Item Quantity",
    "supplier_reliability_score", "supplier_delay_rate",
    "composite_risk_score",
    "order_month", "order_day_of_week", "order_is_weekend",
] + GRAPH_CONTEXT_FEATURES

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


def build_stockout_target(df: pd.DataFrame) -> pd.Series:
    """
    Constructs binary stockout risk target for the Inventory Agent.

    stockout_risk_flag = 1 when either:
      (a) inventory stress is critical AND demand spiked, or
      (b) reorder point is imminent (< 3 days)
    """
    stress_cond = (
        df["inventory_stress_index"] < 0.3 if "inventory_stress_index" in df.columns
        else pd.Series(False, index=df.index)
    )
    spike_cond = (
        df["demand_spike_flag"] == 1 if "demand_spike_flag" in df.columns
        else pd.Series(False, index=df.index)
    )
    reorder_cond = (
        df["days_until_reorder"] < 3 if "days_until_reorder" in df.columns
        else pd.Series(False, index=df.index)
    )
    return ((stress_cond & spike_cond) | reorder_cond).astype(int)


def prepare_features(
    df: pd.DataFrame,
    feature_config: FeatureConfig,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Prepare feature matrix X and target vector y from dataframe.

    Returns only rows where all features and target are non-null.
    """
    # Build synthetic target for Inventory Agent if missing
    if feature_config.target == "stockout_risk_flag" and feature_config.target not in df.columns:
        df = df.copy()
        df["stockout_risk_flag"] = build_stockout_target(df)

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

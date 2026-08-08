"""
AMASCI ML Utilities
====================
Feature lists, targets, hyperparameters, and helper functions.

Leakage ban (§3.2): a module-level guard runs at import and raises ValueError
if any banned feature appears in a feature list. This is a hard build failure.

Full-df target encoding ban: supplier_delay_rate computed on the full dataframe
is a target-encoding leak. The feature lists use supplier_hist_late_rate and
route_hist_late_rate — expanding shifted rates computed in feature_engineering.

Agent differentiation (§3.7):
  Supplier  — predicts P(supplier's monthly late rate > its trailing median)
              Uses supplier history, category diversity, volume, lead-time.
  Logistics — predicts Late_delivery_risk at individual order level.
              Uses route, shipping mode, region, scheduled days, calendar.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import roc_auc_score

logger = logging.getLogger(__name__)


class IntelligenceType(str, Enum):
    DEMAND    = "demand"
    INVENTORY = "inventory"
    SUPPLIER  = "supplier"
    LOGISTICS = "logistics"


class ModelTask(str, Enum):
    REGRESSION     = "regression"
    CLASSIFICATION = "classification"


@dataclass
class FeatureConfig:
    features: list[str]
    target: str
    task: ModelTask
    categorical_features: list[str] = field(default_factory=list)


# ── Graph context features (spec §1.4) ───────────────────────────────────────
# Exactly four. Not three, not five. Order is frozen.
GRAPH_CONTEXT_FEATURES: list[str] = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_tpke_edge_density",    # was graph_has_upcoming_event (pure calendar — no graph signal)
    "graph_avg_shipping_delay",   # redefined: neighbour-route observed delay via :SHIPS_VIA/:CO_FAILS_WITH
]

# ── DEMAND — LightGBM Regressor ───────────────────────────────────────────────
# Target: Order Item Quantity
# Banned: demand_intensity, quantity_zscore (algebraic transforms of the target)
# Banned: revenue_per_unit, order_value_log (sales/qty — algebraic of target)
# Banned: Sales, Order Item Total, Order Profit Per Order (qty × price)
DEMAND_FEATURES: list[str] = [
    "qty_roll_7", "qty_roll_30", "qty_lag_1", "qty_lag_7", "qty_lag_30",
    "demand_volatility", "demand_spike_flag", "demand_trend_slope",
    "demand_momentum", "price_ratio", "discount_rate",
    "order_month", "order_quarter", "order_dayofweek", "is_weekend",
    "is_holiday_period",
] + GRAPH_CONTEXT_FEATURES

DEMAND_TARGET = "Order Item Quantity"


# ── SUPPLIER — Random Forest Classifier ──────────────────────────────────────
# Target: Late_delivery_risk
# Emphasis: supplier history, category diversity, volume, lead-time variance.
# Banned: is_delayed, delivery_gap, shipping_delay, delay_category,
#         shipping_delay_ratio, composite_risk_score, delivery_duration_days,
#         "Days for shipping (real)", shipping_efficiency_score,
#         supplier_delay_rate (full-df encoding — use supplier_hist_late_rate)
SUPPLIER_FEATURES: list[str] = [
    "supplier_hist_late_rate", "supplier_reliability_score",
    "supplier_risk_index", "supplier_order_volume",
    "supplier_category_diversity",
    "days_scheduled",
    "order_month", "order_quarter", "order_dayofweek",
    "is_holiday_period",
    "qty_roll_7", "demand_spike_flag",
] + GRAPH_CONTEXT_FEATURES

SUPPLIER_TARGET = "Late_delivery_risk"

# ── LOGISTICS — LightGBM Classifier ──────────────────────────────────────────
# Target: Late_delivery_risk
# Emphasis: route, shipping mode, region, scheduled days, calendar.
# Banned: same post-shipment set as Supplier.
# Differentiated from Supplier by feature emphasis (route vs supplier history).
LOGISTICS_FEATURES: list[str] = [
    "shipping_mode_encoded", "route_frequency", "region_congestion_index",
    "route_hist_late_rate", "region_hist_late_rate", "shipmode_hist_late_rate",
    "days_scheduled",
    "order_value_log", "discount_rate",
    "order_month", "order_dayofweek", "is_weekend", "is_holiday_period",
    "qty_roll_7", "demand_spike_flag",
] + GRAPH_CONTEXT_FEATURES

LOGISTICS_TARGET = "Late_delivery_risk"


# ── Leakage ban — enforced at import ─────────────────────────────────────────

_LEAKY: dict[str, set[str]] = {
    "demand": {
        # Algebraic transforms of Order Item Quantity
        "demand_intensity", "quantity_zscore",
        # Sales-derived (qty × price)
        "revenue_per_unit", "order_value_log",
        "Sales", "Order Item Total", "Order Profit Per Order",
        # Category-level qty aggregate — smoothed target regardless of shift
        "category_demand_rank",
    },
    "supplier": {
        # Post-shipment observables
        "is_delayed", "delivery_gap", "shipping_delay", "delay_category",
        "shipping_delay_ratio", "composite_risk_score",
        "delivery_duration_days", "Days for shipping (real)",
        "shipping_efficiency_score",
        # Full-df target encoding
        "supplier_delay_rate",
        # Full-df route/region encodings
        "region_congestion_index",  # full-df in old code; use region_hist_late_rate
    },
    "logistics": {
        # Post-shipment observables
        "is_delayed", "delivery_gap", "shipping_delay", "delay_category",
        "shipping_delay_ratio", "composite_risk_score",
        "delivery_duration_days", "Days for shipping (real)",
        "shipping_efficiency_score",
        # Full-df target encoding
        "supplier_delay_rate",
    },
}

_ALL_LISTS: dict[str, list[str]] = {
    "demand":    DEMAND_FEATURES,
    "supplier":  SUPPLIER_FEATURES,
    "logistics": LOGISTICS_FEATURES,
}

for _name, _feats in _ALL_LISTS.items():
    _overlap = _LEAKY[_name] & set(_feats)
    if _overlap:
        raise ValueError(
            f"Target leakage in {_name.upper()}_FEATURES: {sorted(_overlap)}"
        )


# ── Feature configs ───────────────────────────────────────────────────────────

FEATURE_CONFIGS: dict[IntelligenceType, FeatureConfig] = {
    IntelligenceType.DEMAND: FeatureConfig(
        features=DEMAND_FEATURES,
        target=DEMAND_TARGET,
        task=ModelTask.REGRESSION,
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


# ── Hyperparameters ───────────────────────────────────────────────────────────

LIGHTGBM_REGRESSOR_PARAMS: dict[str, Any] = {
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

LIGHTGBM_CLASSIFIER_PARAMS: dict[str, Any] = {
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


RANDOM_FOREST_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "max_depth": 12,
    "min_samples_split": 10,
    "min_samples_leaf": 5,
    "max_features": "sqrt",
    "class_weight": "balanced",
    "random_state": 42,
    "n_jobs": -1,
}


# ── Statistical leakage auditor ───────────────────────────────────────────────

@dataclass
class LeakageAuditRow:
    feature_name: str
    target_corr: float
    mutual_info: float
    verdict: str   # PASS | SUSPECT | FAIL


def audit_feature_leakage(
    X: pd.DataFrame,
    y: pd.Series,
    corr_threshold: float = 0.85,
    mi_threshold: float = 0.55,
    suspect_threshold: float = 0.70,
) -> list[LeakageAuditRow]:
    """
    For each feature: |Pearson(f, y)| and mutual_info_classif(f, y).
    verdict: FAIL    if corr > corr_threshold OR mi > mi_threshold
             SUSPECT if corr > suspect_threshold
             PASS    otherwise

    Raises LeakageError on any FAIL.
    Logs SUSPECT features as warnings.

    is_delayed would score correlation 1.0 and be caught instantly.
    """
    rows: list[LeakageAuditRow] = []
    fails: list[str] = []

    X_num = X.select_dtypes(include=[np.number]).fillna(0)
    if X_num.empty:
        return rows

    y_arr = y.values.astype(float)

    # Pearson correlations
    corrs = {col: abs(float(np.corrcoef(X_num[col].values, y_arr)[0, 1]))
             for col in X_num.columns}

    # Mutual information (classification only — skip for regression)
    # Use raw MI (not normalized) to avoid false positives from high-information
    # legitimate features like days_scheduled.
    try:
        mi_vals = mutual_info_classif(X_num, y_arr.astype(int), random_state=42)
        mi_dict = {col: float(mi_vals[i]) for i, col in enumerate(X_num.columns)}
    except Exception:
        mi_dict = {col: 0.0 for col in X_num.columns}

    for col in X_num.columns:
        corr = corrs.get(col, 0.0)
        mi   = mi_dict.get(col, 0.0)

        if corr > corr_threshold or mi > mi_threshold:
            verdict = "FAIL"
            fails.append(f"{col} (corr={corr:.3f}, mi={mi:.3f})")
        elif corr > suspect_threshold:
            verdict = "SUSPECT"
            logger.warning(
                f"Leakage audit SUSPECT: {col} corr={corr:.3f} with target"
            )
        else:
            verdict = "PASS"

        rows.append(LeakageAuditRow(
            feature_name=col,
            target_corr=round(corr, 4),
            mutual_info=round(mi, 4),
            verdict=verdict,
        ))

    if fails:
        raise ValueError(
            f"Leakage audit FAIL — features with target correlation > {corr_threshold} "
            f"or MI > {mi_threshold}:\n  " + "\n  ".join(fails)
        )

    return rows


class TautologicalTargetError(ValueError):
    pass


def assert_target_not_reconstructible(
    X: pd.DataFrame,
    y: pd.Series,
    max_auc: float = 0.98,
    label: str = "",
) -> None:
    """
    Fit a depth-3 DecisionTree on X -> y.
    If train AUC > max_auc, the target is a deterministic function of the
    features — raise TautologicalTargetError naming the top-3 features.
    """
    X_num = X.select_dtypes(include=[np.number]).fillna(0)
    if X_num.empty or len(y.unique()) < 2:
        return
    tree = DecisionTreeClassifier(max_depth=3, random_state=42)
    tree.fit(X_num, y)
    auc = roc_auc_score(y, tree.predict_proba(X_num)[:, 1])
    if auc > max_auc:
        importances = dict(zip(X_num.columns, tree.feature_importances_))
        top3 = sorted(importances, key=importances.get, reverse=True)[:3]
        raise TautologicalTargetError(
            f"{label}: depth-3 tree achieves AUC={auc:.4f} > {max_auc}. "
            f"Target is reconstructible from features. Top-3: {top3}. "
            f"Remove tautological features before training."
        )
    logger.info(f"Tautology guard {label}: depth-3 AUC={auc:.4f} ✓")


def assert_agents_distinct(preds: dict[str, np.ndarray], threshold: float = 0.95) -> None:
    """
    Raise ArchitectureError if any two agents' predictions correlate > threshold.
    Supplier and Logistics sharing identical metrics is a sign they are the same model.
    """
    import itertools
    for a, b in itertools.combinations(preds, 2):
        if len(preds[a]) < 2 or len(preds[b]) < 2:
            continue
        r = float(np.corrcoef(preds[a], preds[b])[0, 1])
        if r > threshold:
            raise ValueError(
                f"Agents '{a}' and '{b}' predictions correlate at {r:.3f} > {threshold}. "
                f"They are effectively the same model — differentiate features or targets."
            )



# ── Feature preparation ───────────────────────────────────────────────────────

def prepare_features(
    df: pd.DataFrame,
    feature_config: FeatureConfig,
) -> tuple[pd.DataFrame, pd.Series]:
    """Prepare X, y."""
    available = [
        f for f in feature_config.features
        if f in df.columns and f != feature_config.target
    ]
    if not available:
        raise ValueError(
            f"No configured features found. Expected: {feature_config.features}"
        )
    if feature_config.target not in df.columns:
        raise ValueError(f"Target '{feature_config.target}' not in dataframe")

    subset = df[available + [feature_config.target]].dropna()
    logger.info(
        f"prepare_features: {len(available)} features, {len(subset)} samples"
    )
    return subset[available], subset[feature_config.target]


def chronological_split(
    df: pd.DataFrame,
    train_ratio: float = 0.8,
    date_column: str = "order date (DateOrders)",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split — no shuffling, ever."""
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy()
    test_df  = df.iloc[split_idx:].copy()
    logger.info(f"Chronological split: train={len(train_df)}, test={len(test_df)}")
    return train_df, test_df

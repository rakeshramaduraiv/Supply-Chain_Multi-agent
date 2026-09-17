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
  Supplier  — predicts Late_delivery_risk using supplier-history features:
              hist late rate, category diversity, order volume, lead-time.
              Differentiated from Logistics by feature emphasis, not target.
  Logistics — predicts Late_delivery_risk using route/mode/region features:
              route hist late rate, shipping mode, region congestion, calendar.
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
# Three active graph channels. graph_tpke_edge_density is excluded:
# it is currently nunique=1, std=0.0 (constant until run_drift_experiment
# creates TPKE edges). Re-add it to this list AND to _VARIANCE_CHECKED_COLS
# in enrichment.py simultaneously after the drift experiment confirms real
# variance. Never add a feature here while it is exempt from the variance guard.
GRAPH_CONTEXT_FEATURES: list[str] = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_avg_shipping_delay",
]

# ── DEMAND — LightGBM Regressor ───────────────────────────────────────────────
# Target: Order Item Quantity
# Banned: demand_intensity, quantity_zscore (algebraic transforms of the target)
# Banned: revenue_per_unit, order_value_log (sales/qty — algebraic of target)
# Banned: Sales, Order Item Total, Order Profit Per Order (qty × price)
DEMAND_FEATURES: list[str] = [
    "qty_roll_7", "qty_roll_30", "qty_lag_1", "qty_lag_7", "qty_lag_30",
    "demand_volatility", "demand_spike_flag", "demand_trend_slope",
    "demand_momentum",
    "order_month", "order_quarter", "order_dayofweek", "order_year",
    "is_weekend", "is_holiday_period",
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
        # Algebraic function of the target via Order Item Discount:
        # Order Item Discount = Product Price x Discount Rate x Quantity
        "discount_rate", "price_ratio",
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
        # Categorical perfect-mapping of target
        "Delivery Status",
    },
    "logistics": {
        # Post-shipment observables
        "is_delayed", "delivery_gap", "shipping_delay", "delay_category",
        "shipping_delay_ratio", "composite_risk_score",
        "delivery_duration_days", "Days for shipping (real)",
        "shipping_efficiency_score",
        # Full-df target encoding
        "supplier_delay_rate",
        # Categorical perfect-mapping of target
        "Delivery Status",
    },
}

_ALL_LISTS: dict[str, list[str]] = {
    "demand":    DEMAND_FEATURES,
    "supplier":  SUPPLIER_FEATURES,
    "logistics": LOGISTICS_FEATURES,
}

# Assert no feature list intersects BANNED_FROM_MODELS
try:
    from app.core.constants import BANNED_FROM_MODELS as _BANNED
    for _name, _feats in _ALL_LISTS.items():
        _banned_overlap = set(_BANNED) & set(_feats)
        if _banned_overlap:
            raise ValueError(
                f"BANNED_FROM_MODELS violation in {_name.upper()}_FEATURES: "
                f"{sorted(_banned_overlap)}. "
                f"Remove these columns from the feature list."
            )
except ImportError:
    pass  # constants not yet available during bootstrap

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
    "objective": "huber",       # robust to outlier order quantities
    "alpha": 0.9,               # huber quantile — focus on bulk of distribution
    "metric": "huber",
    "boosting_type": "gbdt",
    "n_estimators": 1000,
    "learning_rate": 0.02,      # lower LR + more trees → better generalisation
    "max_depth": -1,            # let num_leaves control complexity
    "num_leaves": 31,           # reduced from 63 — less overfitting
    "min_child_samples": 20,    # was 50 — too conservative for demand patterns
    "subsample": 0.7,
    "subsample_freq": 1,
    "colsample_bytree": 0.7,
    "reg_alpha": 0.05,
    "reg_lambda": 1.0,          # stronger L2 to reduce variance
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}

LIGHTGBM_CLASSIFIER_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "metric": "binary_logloss",
    "boosting_type": "gbdt",
    "n_estimators": 800,
    "learning_rate": 0.02,
    "max_depth": -1,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.7,
    "subsample_freq": 1,
    "colsample_bytree": 0.7,
    "reg_alpha": 0.05,
    "reg_lambda": 1.0,
    "is_unbalance": True,       # handles class imbalance in Late_delivery_risk
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}


RANDOM_FOREST_PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "max_depth": 15,            # deeper trees capture supplier history patterns
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "max_features": "sqrt",
    "class_weight": "balanced_subsample",  # per-tree rebalancing
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


def _cramers_v(series: pd.Series, y: pd.Series) -> float:
    """
    Cramér's V between a categorical series and a binary target.
    Returns a value in [0, 1]; 1.0 = perfect association.
    """
    try:
        from scipy.stats import chi2_contingency
        ct = pd.crosstab(series.astype(str), y)
        chi2, _, _, _ = chi2_contingency(ct)
        n = len(series)
        k = min(ct.shape) - 1
        if n == 0 or k == 0:
            return 0.0
        return float(np.sqrt(chi2 / (n * k)))
    except Exception:
        return 0.0


def audit_feature_leakage(
    X: pd.DataFrame,
    y: pd.Series,
    corr_threshold: float = 0.85,
    mi_threshold: float = 0.55,
    suspect_threshold: float = 0.70,
    cramers_v_threshold: float = 0.85,
) -> list[LeakageAuditRow]:
    """
    For each numeric feature: |Pearson(f, y)| and mutual_info_classif(f, y).
    For each categorical (object/category) feature: Cramér's V against y.

    verdict: FAIL    if corr > corr_threshold OR mi > mi_threshold
                     OR cramers_v > cramers_v_threshold
             SUSPECT if corr > suspect_threshold
             PASS    otherwise

    Raises ValueError on any FAIL.
    Logs SUSPECT features as warnings.

    is_delayed would score correlation 1.0 and be caught instantly.
    "Delivery Status" would score Cramér's V ≈ 1.0 and be caught here.
    """
    rows: list[LeakageAuditRow] = []
    fails: list[str] = []

    y_arr = y.values.astype(float)

    # ── Categorical path: Cramér's V ─────────────────────────────────────────
    X_cat = X.select_dtypes(include=["object", "category"])
    for col in X_cat.columns:
        cv = _cramers_v(X_cat[col], y)
        if cv > cramers_v_threshold:
            verdict = "FAIL"
            fails.append(f"{col} (cramers_v={cv:.3f})")
        else:
            verdict = "PASS"
        rows.append(LeakageAuditRow(
            feature_name=col,
            target_corr=round(cv, 4),   # reuse field; semantics differ for categoricals
            mutual_info=0.0,
            verdict=verdict,
        ))
        if verdict == "FAIL":
            logger.error(f"Leakage audit FAIL (categorical): {col} Cramér's V={cv:.3f}")

    # ── Numeric path: Pearson + MI ────────────────────────────────────────────
    X_num = X.select_dtypes(include=[np.number]).fillna(0)
    if X_num.empty:
        if fails:
            raise ValueError(
                f"Leakage audit FAIL — categorical features with Cramér's V > {cramers_v_threshold}:\n  "
                + "\n  ".join(fails)
            )
        return rows

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
            f"Leakage audit FAIL — features exceeding thresholds:\n  "
            + "\n  ".join(fails)
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
    if date_column in df.columns:
        dates = pd.to_datetime(df[date_column], errors="coerce")
        assert dates.is_monotonic_increasing, (
            f"chronological_split requires a date-sorted frame. "
            f"Sort by '{date_column}' before calling this function."
        )
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy()
    test_df  = df.iloc[split_idx:].copy()
    logger.info(f"Chronological split: train={len(train_df)}, test={len(test_df)}")
    return train_df, test_df

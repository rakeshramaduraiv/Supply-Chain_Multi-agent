"""
scripts/evaluate_holdout.py
============================
Compute real ML metrics on the four held-out months by running the trained
models directly on each holdout CSV.

For each month:
  1. Load the holdout CSV.
  2. Run engineer_features_on_test(holdout, train) so rolling/expanding stats
     are anchored on the training frame — no future leakage.
  3. Load the active supplier and logistics models from the registry.
  4. Predict on the engineered holdout rows.
  5. Compute AUC, F1, Brier for supplier and logistics.
  6. Compute MAE, RMSE, R² for demand (Order Item Quantity).
  7. Patch those values into replay_results.csv in-place.

Usage:
    docker exec amasci-api-dev python scripts/evaluate_holdout.py
"""
from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("evaluate_holdout")

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

ACTUALS_DIR = BACKEND / "data" / "actuals_real"
TRAIN_CSV   = BACKEND / "data" / "raw" / "DataCoSupplyChainDataset_train.csv"
RESULTS_CSV = ACTUALS_DIR / "replay_results.csv"

MONTH_FILE_MAP = {
    "2017-10": "2017_10_actual.csv",
    "2017-11": "2017_11_actual.csv",
    "2017-12": "2017_12_actual.csv",
    "2018-01": "2018_01_actual.csv",
}


def _load_train() -> pd.DataFrame:
    logger.info(f"Loading training CSV: {TRAIN_CSV}")
    df = pd.read_csv(TRAIN_CSV, encoding="latin-1")
    logger.info(f"  {len(df):,} rows loaded")
    return df


def _load_holdout(month: str) -> pd.DataFrame:
    path = ACTUALS_DIR / MONTH_FILE_MAP[month]
    df = pd.read_csv(path, encoding="latin-1")
    logger.info(f"  {month}: {len(df):,} rows")
    return df


def _engineer(train_df: pd.DataFrame, holdout_df: pd.DataFrame) -> pd.DataFrame:
    from app.feature_engineering import engineer_features_on_test
    return engineer_features_on_test(holdout_df, train_df)


def _load_active_models() -> dict:
    import json
    reg_path = BACKEND / "data" / "models" / "registry.json"
    registry = json.loads(reg_path.read_text())
    models = {}
    import joblib
    for intel_type, versions in registry.items():
        active = next((v for v in reversed(versions) if v.get("is_active")), None)
        if active is None and versions:
            active = versions[-1]
        if active:
            model_path = BACKEND / active["model_path"]
            if model_path.exists():
                models[intel_type] = {
                    "model": joblib.load(model_path),
                    "features": active["features_used"],
                    "task": active.get("task", "classification"),
                }
                logger.info(f"  Loaded {intel_type} model: {model_path.name}")
    return models


def _safe_features(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Return df with only the model's features, filling missing cols and NaNs with 0."""
    available = [f for f in features if f in df.columns]
    missing = [f for f in features if f not in df.columns]
    if missing:
        logger.warning(f"  Missing features (filled with 0): {missing}")
    X = df[available].copy()
    for f in missing:
        X[f] = 0.0
    X = X[features].fillna(0.0)  # fill any NaN produced by rolling/expanding on short windows
    return X


def _eval_classifier(model, X: pd.DataFrame, y: pd.Series) -> dict:
    from sklearn.metrics import roc_auc_score, f1_score, brier_score_loss
    if len(y.unique()) < 2:
        return {"auc": None, "f1": None, "brier": None}
    proba = model.predict_proba(X)[:, 1]
    pred  = (proba >= 0.5).astype(int)
    return {
        "auc":   round(float(roc_auc_score(y, proba)), 4),
        "f1":    round(float(f1_score(y, pred, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(y, proba)), 4),
    }


def _eval_regressor(model, X: pd.DataFrame, y: pd.Series) -> dict:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    pred = model.predict(X)
    return {
        "mae":  round(float(mean_absolute_error(y, pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y, pred))), 4),
        "r2":   round(float(r2_score(y, pred)), 4),
    }


def evaluate_month(
    month: str,
    train_df: pd.DataFrame,
    models: dict,
) -> dict:
    logger.info(f"\n=== {month} ===")
    holdout_df = _load_holdout(month)
    eng_df = _engineer(train_df, holdout_df)

    result: dict = {}

    # Supplier
    if "supplier" in models:
        m = models["supplier"]
        target = "Late_delivery_risk"
        if target in eng_df.columns:
            X = _safe_features(eng_df, m["features"])
            y = eng_df[target].fillna(0).astype(int)
            metrics = _eval_classifier(m["model"], X, y)
            result.update({
                "supplier_auc":   metrics["auc"],
                "supplier_f1":    metrics["f1"],
                "supplier_brier": metrics["brier"],
            })
            logger.info(f"  supplier  auc={metrics['auc']}  f1={metrics['f1']}  brier={metrics['brier']}")

    # Logistics
    if "logistics" in models:
        m = models["logistics"]
        target = "Late_delivery_risk"
        if target in eng_df.columns:
            X = _safe_features(eng_df, m["features"])
            y = eng_df[target].fillna(0).astype(int)
            metrics = _eval_classifier(m["model"], X, y)
            result.update({
                "logistics_auc":   metrics["auc"],
                "logistics_f1":    metrics["f1"],
                "logistics_brier": metrics["brier"],
            })
            logger.info(f"  logistics auc={metrics['auc']}  f1={metrics['f1']}  brier={metrics['brier']}")

    # Demand
    if "demand" in models:
        m = models["demand"]
        target = "Order Item Quantity"
        if target in eng_df.columns:
            X = _safe_features(eng_df, m["features"])
            y = eng_df[target].fillna(0).astype(float)
            metrics = _eval_regressor(m["model"], X, y)
            result.update({
                "demand_mae":  metrics["mae"],
                "demand_rmse": metrics["rmse"],
                "demand_r2":   metrics["r2"],
            })
            logger.info(f"  demand    mae={metrics['mae']}  rmse={metrics['rmse']}  r2={metrics['r2']}")

    return result


def patch_results_csv(month_metrics: dict[str, dict]) -> None:
    """Read replay_results.csv, patch metric columns, write back."""
    if not RESULTS_CSV.exists():
        logger.error(f"replay_results.csv not found at {RESULTS_CSV}")
        return

    METRIC_COLS = [
        "demand_mae", "demand_rmse", "demand_r2",
        "supplier_auc", "supplier_f1", "supplier_brier",
        "logistics_auc", "logistics_f1", "logistics_brier",
    ]

    rows = []
    with open(RESULTS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            month = row.get("month", "")
            if month in month_metrics:
                for col, val in month_metrics[month].items():
                    if col in fieldnames and val is not None:
                        row[col] = str(val)
            rows.append(row)

    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"\nPatched {RESULTS_CSV}")


def main() -> None:
    if not TRAIN_CSV.exists():
        logger.error(f"Training CSV not found: {TRAIN_CSV}")
        sys.exit(1)

    train_df = _load_train()
    logger.info("Loading active models from registry...")
    models = _load_active_models()

    if not models:
        logger.error("No models found in registry. Run retrain first.")
        sys.exit(1)

    month_metrics: dict[str, dict] = {}
    for month in ["2017-10", "2017-11", "2017-12", "2018-01"]:
        try:
            month_metrics[month] = evaluate_month(month, train_df, models)
        except Exception as e:
            logger.error(f"  {month} failed: {e}", exc_info=True)
            month_metrics[month] = {}

    patch_results_csv(month_metrics)

    print("\n=== HOLDOUT EVALUATION SUMMARY ===")
    print(f"{'Month':<10} {'SupAUC':>8} {'SupF1':>7} {'LogAUC':>8} {'LogF1':>7} {'DemMAE':>8} {'DemR2':>7}")
    print("-" * 60)
    for month, m in month_metrics.items():
        print(
            f"{month:<10}"
            f"{str(m.get('supplier_auc', '—')):>8}"
            f"{str(m.get('supplier_f1', '—')):>7}"
            f"{str(m.get('logistics_auc', '—')):>8}"
            f"{str(m.get('logistics_f1', '—')):>7}"
            f"{str(m.get('demand_mae', '—')):>8}"
            f"{str(m.get('demand_r2', '—')):>7}"
        )


if __name__ == "__main__":
    main()

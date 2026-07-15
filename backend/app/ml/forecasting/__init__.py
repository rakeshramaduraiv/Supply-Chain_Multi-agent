"""
AMASCI Forecasting Module
============================
Time-series forecasting for demand, risk, and operational metrics.

Generates:
- Historical predictions (backtest)
- Monthly forecasts
- Future period forecasts with confidence intervals
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.ml.confidence import (
    compute_classification_confidence,
    compute_regression_confidence,
)
from app.ml.registry import ModelRegistry
from app.ml.utils import FEATURE_CONFIGS, IntelligenceType, ModelTask

logger = logging.getLogger(__name__)


@dataclass
class ForecastPeriod:
    """Forecast for a single time period."""
    period: str
    predicted_value: float
    confidence_score: float
    lower_bound: float
    upper_bound: float
    risk_level: str = ""


@dataclass
class ForecastResult:
    """Complete forecast result."""
    intelligence_type: str
    model_version: str
    forecast_periods: list[ForecastPeriod]
    historical_periods: list[ForecastPeriod] = field(default_factory=list)
    mean_confidence: float = 0.0
    forecast_horizon: int = 0
    generation_time_ms: float = 0.0
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intelligence_type": self.intelligence_type,
            "model_version": self.model_version,
            "forecast_horizon": self.forecast_horizon,
            "mean_confidence": round(self.mean_confidence, 4),
            "generation_time_ms": round(self.generation_time_ms, 2),
            "generated_at": self.generated_at,
            "forecast_periods": [
                {
                    "period": fp.period,
                    "predicted_value": round(fp.predicted_value, 4),
                    "confidence_score": round(fp.confidence_score, 4),
                    "lower_bound": round(fp.lower_bound, 4),
                    "upper_bound": round(fp.upper_bound, 4),
                    "risk_level": fp.risk_level,
                }
                for fp in self.forecast_periods
            ],
            "historical_periods": [
                {
                    "period": hp.period,
                    "predicted_value": round(hp.predicted_value, 4),
                    "confidence_score": round(hp.confidence_score, 4),
                    "lower_bound": round(hp.lower_bound, 4),
                    "upper_bound": round(hp.upper_bound, 4),
                    "risk_level": hp.risk_level,
                }
                for hp in self.historical_periods
            ],
        }


class ForecastEngine:
    """
    Forecasting engine for generating period-level predictions.

    Supports:
    - Monthly aggregated forecasts
    - Historical backtesting
    - Future period extrapolation with confidence bounds
    """

    def __init__(self, registry: ModelRegistry | None = None):
        self.registry = registry or ModelRegistry()

    def forecast_monthly(
        self,
        df: pd.DataFrame,
        intelligence_type: IntelligenceType,
        horizon_months: int = 3,
        version_id: str | None = None,
    ) -> ForecastResult:
        """
        Generate monthly forecasts.

        Uses historical monthly patterns to predict future periods.
        """
        start_time = time.perf_counter()
        feature_config = FEATURE_CONFIGS[intelligence_type]

        model = self.registry.load_model(intelligence_type, version_id)
        version = self.registry.get_version(intelligence_type, version_id)
        model_version = version.version_id if version else "unknown"

        # Generate historical monthly predictions
        historical_periods = self._backtest_monthly(df, model, feature_config)

        # Generate future forecasts
        forecast_periods = self._forecast_future(
            df, model, feature_config, horizon_months
        )

        all_confidences = [
            fp.confidence_score for fp in forecast_periods + historical_periods
        ]
        mean_confidence = float(np.mean(all_confidences)) if all_confidences else 0.0

        generation_time_ms = (time.perf_counter() - start_time) * 1000

        result = ForecastResult(
            intelligence_type=intelligence_type.value,
            model_version=model_version,
            forecast_periods=forecast_periods,
            historical_periods=historical_periods,
            mean_confidence=mean_confidence,
            forecast_horizon=horizon_months,
            generation_time_ms=generation_time_ms,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            f"Forecast generated: {intelligence_type.value} "
            f"horizon={horizon_months} months, time={generation_time_ms:.1f}ms"
        )
        return result

    def _backtest_monthly(
        self,
        df: pd.DataFrame,
        model: Any,
        feature_config: Any,
    ) -> list[ForecastPeriod]:
        """Generate predictions for historical monthly periods."""
        if "period_monthly" not in df.columns:
            return []

        available_features = [f for f in feature_config.features if f in df.columns]
        if not available_features:
            return []

        periods = sorted(df["period_monthly"].dropna().unique())
        historical = []

        for period in periods[-12:]:  # Last 12 months
            period_df = df[df["period_monthly"] == period]
            X_period = period_df[available_features].fillna(0)

            if len(X_period) == 0:
                continue

            preds = model.predict(X_period)
            mean_pred = float(np.mean(preds))

            # Confidence from prediction variance
            pred_std = float(np.std(preds)) if len(preds) > 1 else 0.0
            confidence = max(0.0, 1.0 - (pred_std / (abs(mean_pred) + 1e-6)))
            confidence = min(confidence, 1.0)

            # Bounds
            lower = mean_pred - 1.96 * pred_std
            upper = mean_pred + 1.96 * pred_std

            risk_level = ""
            if feature_config.task == ModelTask.CLASSIFICATION:
                risk_level = "high" if mean_pred > 0.5 else "low"

            historical.append(ForecastPeriod(
                period=str(period),
                predicted_value=mean_pred,
                confidence_score=confidence,
                lower_bound=lower,
                upper_bound=upper,
                risk_level=risk_level,
            ))

        return historical

    def _forecast_future(
        self,
        df: pd.DataFrame,
        model: Any,
        feature_config: Any,
        horizon_months: int,
    ) -> list[ForecastPeriod]:
        """
        Generate future period forecasts by extrapolating from recent data patterns.

        Uses the most recent month's feature distribution as a template,
        with temporal feature adjustments for future months.
        """
        if "period_monthly" not in df.columns:
            return []

        available_features = [f for f in feature_config.features if f in df.columns]
        if not available_features:
            return []

        periods = sorted(df["period_monthly"].dropna().unique())
        if not periods:
            return []

        # Use last month as template
        last_period = periods[-1]
        template_df = df[df["period_monthly"] == last_period][available_features]

        if len(template_df) == 0:
            return []

        # Get last date for period generation
        last_date = pd.Timestamp.now()
        if "order date (DateOrders)" in df.columns:
            valid_dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce").dropna()
            if len(valid_dates) > 0:
                last_date = valid_dates.max()

        forecast_periods = []
        for i in range(1, horizon_months + 1):
            future_date = last_date + pd.DateOffset(months=i)
            period_label = future_date.strftime("%Y-%m")

            # Create synthetic features for future period
            X_future = template_df.copy()

            # Adjust temporal features
            if "order_month" in X_future.columns:
                X_future["order_month"] = future_date.month
            if "order_quarter" in X_future.columns:
                X_future["order_quarter"] = (future_date.month - 1) // 3 + 1
            if "order_day_of_week" in X_future.columns:
                X_future["order_day_of_week"] = future_date.dayofweek

            X_future = X_future.fillna(0)
            preds = model.predict(X_future)
            mean_pred = float(np.mean(preds))
            pred_std = float(np.std(preds)) if len(preds) > 1 else 0.0

            # Confidence decays with forecast horizon
            base_confidence = max(0.0, 1.0 - (pred_std / (abs(mean_pred) + 1e-6)))
            decay_factor = 0.95 ** i  # 5% decay per month
            confidence = min(base_confidence * decay_factor, 1.0)

            lower = mean_pred - 1.96 * pred_std * (1 + 0.1 * i)
            upper = mean_pred + 1.96 * pred_std * (1 + 0.1 * i)

            risk_level = ""
            if feature_config.task == ModelTask.CLASSIFICATION:
                risk_level = "high" if mean_pred > 0.5 else "low"

            forecast_periods.append(ForecastPeriod(
                period=period_label,
                predicted_value=mean_pred,
                confidence_score=confidence,
                lower_bound=lower,
                upper_bound=upper,
                risk_level=risk_level,
            ))

        return forecast_periods

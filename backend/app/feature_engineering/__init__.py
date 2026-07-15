"""
AMASCI Feature Engineering Module
===================================
22 engineered features derived from DataCo Smart Supply Chain Dataset.

Categories:
- Temporal Intelligence (5 features)
- Shipping Intelligence (3 features)
- Financial Intelligence (4 features)
- Demand Intelligence (4 features)
- Supplier Intelligence (3 features)
- Risk Intelligence (3 features)

Input: Cleaned DataFrame with DataCo columns
Output: DataFrame with 22 engineered features + original columns
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

ENGINEERED_FEATURES = [
    # Temporal Intelligence
    "order_month",
    "order_day_of_week",
    "order_week_of_year",
    "order_quarter",
    "order_is_weekend",
    # Shipping Intelligence
    "delivery_duration_days",
    "shipping_delay_ratio",
    "is_delayed",
    # Financial Intelligence
    "profit_margin_pct",
    "discount_impact",
    "revenue_per_unit",
    "order_value_log",
    # Demand Intelligence
    "quantity_zscore",
    "price_quantity_interaction",
    "demand_intensity",
    "category_demand_rank",
    # Supplier Intelligence
    "supplier_volume",
    "supplier_delay_rate",
    "supplier_risk_index",
    # Risk Intelligence
    "composite_risk_score",
    "delivery_gap",
    "period_monthly",
]


class FeatureEngineeringPipeline:
    """
    Transforms raw DataCo dataset into 22 ML-ready engineered features.

    Usage:
        pipeline = FeatureEngineeringPipeline()
        df_engineered = pipeline.transform(df_cleaned)
    """

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all feature engineering transformations.

        Returns DataFrame with original columns + 22 engineered features.
        """
        logger.info(f"Feature engineering: {len(df)} rows, {len(df.columns)} columns")
        result = df.copy()

        result = self._temporal_features(result)
        result = self._shipping_features(result)
        result = self._financial_features(result)
        result = self._demand_features(result)
        result = self._supplier_features(result)
        result = self._risk_features(result)

        engineered_count = sum(1 for f in ENGINEERED_FEATURES if f in result.columns)
        logger.info(f"Feature engineering complete: {engineered_count}/22 features created")
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # TEMPORAL INTELLIGENCE (5 features)
    # ─────────────────────────────────────────────────────────────────────────

    def _temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract temporal features from order date."""
        date_col = "order date (DateOrders)"
        if date_col not in df.columns:
            logger.warning(f"Missing '{date_col}' — skipping temporal features")
            return df

        dates = pd.to_datetime(df[date_col], errors="coerce")

        df["order_month"] = dates.dt.month.fillna(1).astype(int)
        df["order_day_of_week"] = dates.dt.dayofweek.fillna(0).astype(int)
        df["order_week_of_year"] = dates.dt.isocalendar().week.fillna(1).astype(int)
        df["order_quarter"] = dates.dt.quarter.fillna(1).astype(int)
        df["order_is_weekend"] = (dates.dt.dayofweek >= 5).astype(int)

        # Monthly period label for forecasting
        df["period_monthly"] = dates.dt.to_period("M").astype(str)

        logger.info("Temporal features: 5 created")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # SHIPPING INTELLIGENCE (3 features)
    # ─────────────────────────────────────────────────────────────────────────

    def _shipping_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute shipping performance features."""
        real_col = "Days for shipping (real)"
        sched_col = "Days for shipment (scheduled)"

        if real_col in df.columns and sched_col in df.columns:
            real = df[real_col].fillna(0)
            sched = df[sched_col].fillna(1)

            # Duration in days
            df["delivery_duration_days"] = real

            # Ratio: actual / scheduled (>1 means delayed)
            df["shipping_delay_ratio"] = np.where(
                sched > 0, real / sched, 1.0
            )

            # Binary: is the shipment delayed?
            df["is_delayed"] = (real > sched).astype(int)
        else:
            df["delivery_duration_days"] = 0
            df["shipping_delay_ratio"] = 1.0
            df["is_delayed"] = 0

        logger.info("Shipping features: 3 created")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # FINANCIAL INTELLIGENCE (4 features)
    # ─────────────────────────────────────────────────────────────────────────

    def _financial_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute financial performance features."""
        sales = df["Sales"].fillna(0) if "Sales" in df.columns else pd.Series(0, index=df.index)
        profit = df["Order Profit Per Order"].fillna(0) if "Order Profit Per Order" in df.columns else pd.Series(0, index=df.index)
        discount = df["Order Item Discount"].fillna(0) if "Order Item Discount" in df.columns else pd.Series(0, index=df.index)
        quantity = df["Order Item Quantity"].fillna(1) if "Order Item Quantity" in df.columns else pd.Series(1, index=df.index)

        # Profit margin percentage
        df["profit_margin_pct"] = np.where(
            sales > 0, (profit / sales) * 100, 0.0
        )

        # Discount impact: discount relative to sales
        df["discount_impact"] = np.where(
            sales > 0, discount / sales, 0.0
        )

        # Revenue per unit
        df["revenue_per_unit"] = np.where(
            quantity > 0, sales / quantity, 0.0
        )

        # Log-transformed order value (handles skewness)
        df["order_value_log"] = np.log1p(np.maximum(sales, 0))

        logger.info("Financial features: 4 created")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # DEMAND INTELLIGENCE (4 features)
    # ─────────────────────────────────────────────────────────────────────────

    def _demand_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute demand pattern features."""
        qty_col = "Order Item Quantity"
        price_col = "Product Price"
        cat_col = "Category Name"

        quantity = df[qty_col].fillna(0) if qty_col in df.columns else pd.Series(0, index=df.index)
        price = df[price_col].fillna(0) if price_col in df.columns else pd.Series(0, index=df.index)

        # Quantity z-score (how unusual is this order size?)
        qty_mean = quantity.mean()
        qty_std = quantity.std()
        df["quantity_zscore"] = np.where(
            qty_std > 0, (quantity - qty_mean) / qty_std, 0.0
        )

        # Price-quantity interaction (high price + high qty = high demand signal)
        price_norm = np.where(price.max() > 0, price / price.max(), 0.0)
        qty_norm = np.where(quantity.max() > 0, quantity / quantity.max(), 0.0)
        df["price_quantity_interaction"] = price_norm * qty_norm

        # Demand intensity: quantity * price (total demand value)
        df["demand_intensity"] = quantity * price

        # Category demand rank (rank categories by total volume)
        if cat_col in df.columns:
            cat_volume = df.groupby(cat_col)[qty_col].transform("sum") if qty_col in df.columns else 0
            max_vol = cat_volume.max() if hasattr(cat_volume, "max") and cat_volume.max() > 0 else 1
            df["category_demand_rank"] = cat_volume / max_vol
        else:
            df["category_demand_rank"] = 0.5

        logger.info("Demand features: 4 created")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # SUPPLIER INTELLIGENCE (3 features)
    # ─────────────────────────────────────────────────────────────────────────

    def _supplier_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute supplier performance features."""
        dept_col = "Department Name"
        target_col = "Late_delivery_risk"
        real_col = "Days for shipping (real)"
        sched_col = "Days for shipment (scheduled)"

        if dept_col not in df.columns:
            df["supplier_volume"] = 0
            df["supplier_delay_rate"] = 0.0
            df["supplier_risk_index"] = 0.0
            return df

        # Supplier order volume (normalized)
        vol = df.groupby(dept_col)[dept_col].transform("count")
        df["supplier_volume"] = vol / vol.max() if vol.max() > 0 else 0

        # Supplier delay rate (% of late deliveries per supplier)
        if target_col in df.columns:
            df["supplier_delay_rate"] = df.groupby(dept_col)[target_col].transform("mean")
        else:
            df["supplier_delay_rate"] = 0.0

        # Composite supplier risk index
        delay_rate = df["supplier_delay_rate"].fillna(0)
        if real_col in df.columns and sched_col in df.columns:
            avg_delay = df.groupby(dept_col).apply(
                lambda g: (g[real_col] - g[sched_col]).mean()
            )
            delay_map = avg_delay.clip(lower=0)
            max_delay = delay_map.max() if delay_map.max() > 0 else 1
            normalized_delay = df[dept_col].map(delay_map / max_delay).fillna(0)
            df["supplier_risk_index"] = np.clip(
                delay_rate * 0.6 + normalized_delay * 0.4, 0, 1
            )
        else:
            df["supplier_risk_index"] = delay_rate

        logger.info("Supplier features: 3 created")
        return df

    # ─────────────────────────────────────────────────────────────────────────
    # RISK INTELLIGENCE (3 features)
    # ─────────────────────────────────────────────────────────────────────────

    def _risk_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute composite risk features."""
        # Delivery gap: actual - scheduled days
        real_col = "Days for shipping (real)"
        sched_col = "Days for shipment (scheduled)"

        if real_col in df.columns and sched_col in df.columns:
            df["delivery_gap"] = df[real_col].fillna(0) - df[sched_col].fillna(0)
        else:
            df["delivery_gap"] = 0

        # Composite risk score: weighted combination of risk signals
        shipping_risk = df.get("shipping_delay_ratio", pd.Series(1.0, index=df.index))
        supplier_risk = df.get("supplier_risk_index", pd.Series(0.0, index=df.index))
        discount_risk = df.get("discount_impact", pd.Series(0.0, index=df.index))

        # Normalize shipping_delay_ratio to [0,1]
        sr_max = shipping_risk.max() if shipping_risk.max() > 0 else 1
        shipping_norm = np.clip(shipping_risk / sr_max, 0, 1)

        df["composite_risk_score"] = np.clip(
            shipping_norm * 0.4 + supplier_risk * 0.4 + discount_risk * 0.2,
            0, 1
        )

        logger.info("Risk features: 3 created")
        return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Convenience function to run the full feature engineering pipeline."""
    pipeline = FeatureEngineeringPipeline()
    return pipeline.transform(df)

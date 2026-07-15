"""
AMASCI Transformation Service
================================
Date feature extraction, temporal bucketing, aggregation, and window creation.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TransformationReport:
    """Audit trail of transformation operations."""

    columns_added: list[str] = field(default_factory=list)
    columns_removed: list[str] = field(default_factory=list)
    aggregations_created: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns_added": self.columns_added,
            "columns_removed": self.columns_removed,
            "aggregations_created": self.aggregations_created,
            "operations_count": len(self.operations),
        }


class TransformationService:
    """Transforms cleaned data into ML-ready format."""

    def transform(self, df: pd.DataFrame) -> tuple[pd.DataFrame, TransformationReport]:
        """
        Execute full transformation pipeline.

        Steps:
        1. Extract date features
        2. Compute delivery duration
        3. Create period columns (weekly/monthly)
        4. Sort by temporal order
        5. Drop unnecessary columns
        """
        report = TransformationReport()
        df = df.copy()

        df = self._extract_date_features(df, report)
        df = self._compute_delivery_duration(df, report)
        df = self._create_period_columns(df, report)
        df = self._sort_temporal(df, report)
        df = self._drop_unnecessary_columns(df, report)

        logger.info(
            f"Transformation complete: {len(report.columns_added)} columns added",
            extra={"added": len(report.columns_added)},
        )

        return df, report

    def _extract_date_features(self, df: pd.DataFrame, report: TransformationReport) -> pd.DataFrame:
        """Extract temporal components from date columns."""
        order_col = "order date (DateOrders)"
        ship_col = "shipping date (DateOrders)"

        if order_col in df.columns:
            df[order_col] = pd.to_datetime(df[order_col], errors="coerce")

            df["order_year"] = df[order_col].dt.year.astype("Int64")
            df["order_month"] = df[order_col].dt.month.astype("Int64")
            df["order_day"] = df[order_col].dt.day.astype("Int64")
            df["order_day_of_week"] = df[order_col].dt.dayofweek.astype("Int64")
            df["order_week_of_year"] = df[order_col].dt.isocalendar().week.astype("Int64")
            df["order_quarter"] = df[order_col].dt.quarter.astype("Int64")
            df["order_is_weekend"] = (df["order_day_of_week"] >= 5).astype("Int64")

            new_cols = [
                "order_year", "order_month", "order_day",
                "order_day_of_week", "order_week_of_year",
                "order_quarter", "order_is_weekend",
            ]
            report.columns_added.extend(new_cols)
            report.operations.append("Extracted 7 date features from order date")

        if ship_col in df.columns:
            df[ship_col] = pd.to_datetime(df[ship_col], errors="coerce")

            df["ship_year"] = df[ship_col].dt.year.astype("Int64")
            df["ship_month"] = df[ship_col].dt.month.astype("Int64")
            df["ship_day_of_week"] = df[ship_col].dt.dayofweek.astype("Int64")

            new_cols = ["ship_year", "ship_month", "ship_day_of_week"]
            report.columns_added.extend(new_cols)
            report.operations.append("Extracted 3 date features from shipping date")

        return df

    def _compute_delivery_duration(self, df: pd.DataFrame, report: TransformationReport) -> pd.DataFrame:
        """Compute actual delivery duration in days."""
        order_col = "order date (DateOrders)"
        ship_col = "shipping date (DateOrders)"

        if order_col in df.columns and ship_col in df.columns:
            mask = df[order_col].notna() & df[ship_col].notna()
            df.loc[mask, "delivery_duration_days"] = (
                df.loc[mask, ship_col] - df.loc[mask, order_col]
            ).dt.days

            # Ensure non-negative
            if "delivery_duration_days" in df.columns:
                df["delivery_duration_days"] = df["delivery_duration_days"].clip(lower=0)

            report.columns_added.append("delivery_duration_days")
            report.operations.append("Computed delivery_duration_days")

        return df

    def _create_period_columns(self, df: pd.DataFrame, report: TransformationReport) -> pd.DataFrame:
        """Create weekly and monthly period identifiers for temporal grouping."""
        order_col = "order date (DateOrders)"

        if order_col in df.columns and df[order_col].notna().any():
            # Monthly period: YYYY-MM
            df["period_monthly"] = df[order_col].dt.to_period("M").astype(str)
            report.columns_added.append("period_monthly")

            # Weekly period: YYYY-WXX
            df["period_weekly"] = (
                df[order_col].dt.year.astype(str)
                + "-W"
                + df[order_col].dt.isocalendar().week.astype(str).str.zfill(2)
            )
            report.columns_added.append("period_weekly")

            report.operations.append("Created monthly and weekly period columns")

        return df

    def _sort_temporal(self, df: pd.DataFrame, report: TransformationReport) -> pd.DataFrame:
        """Sort dataset by temporal order for walk-forward validation."""
        order_col = "order date (DateOrders)"

        if order_col in df.columns:
            df = df.sort_values(order_col, ascending=True).reset_index(drop=True)
            report.operations.append("Sorted by order date (ascending)")

        return df

    def _drop_unnecessary_columns(self, df: pd.DataFrame, report: TransformationReport) -> pd.DataFrame:
        """Remove columns that provide no analytical value."""
        drop_candidates = [
            "Customer Email",
            "Customer Password",
            "Customer Street",
            "Product Image",
            "Product Description",
            "Customer Fname",
            "Customer Lname",
            "Order Zipcode",
            "Customer Zipcode",
        ]

        dropped = []
        for col in drop_candidates:
            if col in df.columns:
                df = df.drop(columns=[col])
                dropped.append(col)

        if dropped:
            report.columns_removed = dropped
            report.operations.append(f"Dropped {len(dropped)} unnecessary columns")

        return df

    def create_monthly_aggregation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create monthly aggregated metrics for forecasting."""
        if "period_monthly" not in df.columns:
            return pd.DataFrame()

        agg = df.groupby("period_monthly").agg(
            total_orders=("Order Id", "nunique"),
            total_sales=("Sales", "sum"),
            avg_profit=("Order Profit Per Order", "mean"),
            late_delivery_count=("Late_delivery_risk", "sum"),
            total_items=("Order Item Quantity", "sum"),
            avg_shipping_days=("Days for shipping (real)", "mean"),
            avg_scheduled_days=("Days for shipment (scheduled)", "mean"),
        ).reset_index()

        agg["late_delivery_rate"] = (
            agg["late_delivery_count"] / agg["total_orders"]
        ).round(4)

        return agg

    def create_weekly_aggregation(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create weekly aggregated metrics."""
        if "period_weekly" not in df.columns:
            return pd.DataFrame()

        agg = df.groupby("period_weekly").agg(
            total_orders=("Order Id", "nunique"),
            total_sales=("Sales", "sum"),
            late_delivery_count=("Late_delivery_risk", "sum"),
            avg_shipping_days=("Days for shipping (real)", "mean"),
        ).reset_index()

        agg["late_delivery_rate"] = (
            agg["late_delivery_count"] / agg["total_orders"]
        ).round(4)

        return agg

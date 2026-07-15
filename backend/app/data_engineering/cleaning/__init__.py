"""
AMASCI Cleaning Service
=========================
Data cleaning: missing values, duplicates, dates, normalization, business rules.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.core.constants import REQUIRED_COLUMNS, TARGET_COLUMN

logger = logging.getLogger(__name__)


@dataclass
class CleaningReport:
    """Audit trail of all cleaning operations performed."""

    rows_before: int = 0
    rows_after: int = 0
    rows_removed: int = 0
    duplicates_removed: int = 0
    nulls_imputed: dict[str, int] = field(default_factory=dict)
    dates_fixed: int = 0
    negatives_fixed: int = 0
    categories_normalized: int = 0
    operations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "rows_removed": self.rows_removed,
            "duplicates_removed": self.duplicates_removed,
            "nulls_imputed": self.nulls_imputed,
            "dates_fixed": self.dates_fixed,
            "negatives_fixed": self.negatives_fixed,
            "categories_normalized": self.categories_normalized,
            "operations_count": len(self.operations),
            "operations": self.operations,
        }


class CleaningService:
    """Performs data cleaning operations on validated datasets."""

    # Known categorical values for normalization
    VALID_SHIPPING_MODES = {"Standard Class", "First Class", "Second Class", "Same Day"}
    VALID_DELIVERY_STATUS = {
        "Advance shipping", "Late delivery", "Shipping on time", "Shipping canceled"
    }
    VALID_MARKETS = {"Africa", "Europe", "LATAM", "Pacific Asia", "USCA"}
    VALID_SEGMENTS = {"Consumer", "Corporate", "Home Office"}

    def clean(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        """
        Execute full cleaning pipeline.

        Steps:
        1. Remove exact duplicates
        2. Handle missing values
        3. Parse and fix dates
        4. Fix negative values
        5. Normalize categories
        6. Validate business rules
        7. Remove invalid rows
        """
        report = CleaningReport(rows_before=len(df))
        df = df.copy()

        df = self._remove_duplicates(df, report)
        df = self._handle_missing_values(df, report)
        df = self._fix_dates(df, report)
        df = self._fix_negative_values(df, report)
        df = self._normalize_categories(df, report)
        df = self._validate_business_rules(df, report)
        df = self._drop_invalid_rows(df, report)

        report.rows_after = len(df)
        report.rows_removed = report.rows_before - report.rows_after

        logger.info(
            f"Cleaning complete: {report.rows_before} → {report.rows_after} rows",
            extra={
                "removed": report.rows_removed,
                "duplicates": report.duplicates_removed,
            },
        )

        return df, report

    def _remove_duplicates(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """Remove exact duplicate rows."""
        before = len(df)
        df = df.drop_duplicates()
        removed = before - len(df)
        report.duplicates_removed = removed
        if removed > 0:
            report.operations.append(f"Removed {removed} duplicate rows")
        return df

    def _handle_missing_values(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """Impute missing values using type-appropriate strategies."""
        for col in df.columns:
            null_count = int(df[col].isnull().sum())
            if null_count == 0:
                continue

            if col == TARGET_COLUMN:
                # Never impute target - drop rows
                df = df.dropna(subset=[col])
                report.nulls_imputed[col] = null_count
                report.operations.append(f"Dropped {null_count} rows with null target")
                continue

            if df[col].dtype in ["float64", "int64", "float32", "int32"]:
                # Numeric: group-aware median
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                report.nulls_imputed[col] = null_count
                report.operations.append(
                    f"Imputed {null_count} nulls in '{col}' with median ({median_val:.2f})"
                )
            elif df[col].dtype == "object":
                # Categorical: mode
                mode_val = df[col].mode()
                fill_val = mode_val.iloc[0] if not mode_val.empty else "Unknown"
                df[col] = df[col].fillna(fill_val)
                report.nulls_imputed[col] = null_count
                report.operations.append(
                    f"Imputed {null_count} nulls in '{col}' with mode ('{fill_val}')"
                )
            else:
                # Fallback: forward fill then backward fill
                df[col] = df[col].ffill().bfill()
                report.nulls_imputed[col] = null_count
                report.operations.append(f"Imputed {null_count} nulls in '{col}' with ffill/bfill")

        return df

    def _fix_dates(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """Parse date columns and fix temporal inconsistencies."""
        date_cols = ["order date (DateOrders)", "shipping date (DateOrders)"]
        fixes = 0

        for col in date_cols:
            if col not in df.columns:
                continue
            df[col] = pd.to_datetime(df[col], errors="coerce")

        # Fix temporal inconsistency: shipping < order
        if all(c in df.columns for c in date_cols):
            mask = (
                df["shipping date (DateOrders)"].notna()
                & df["order date (DateOrders)"].notna()
                & (df["shipping date (DateOrders)"] < df["order date (DateOrders)"])
            )
            violations = int(mask.sum())
            if violations > 0:
                # Swap dates where difference is small (< 7 days)
                delta = (
                    df.loc[mask, "order date (DateOrders)"]
                    - df.loc[mask, "shipping date (DateOrders)"]
                ).dt.days
                swap_mask = mask & (delta.reindex(df.index, fill_value=0).abs() <= 7)
                swap_count = int(swap_mask.sum())

                if swap_count > 0:
                    temp = df.loc[swap_mask, "order date (DateOrders)"].copy()
                    df.loc[swap_mask, "order date (DateOrders)"] = df.loc[
                        swap_mask, "shipping date (DateOrders)"
                    ]
                    df.loc[swap_mask, "shipping date (DateOrders)"] = temp
                    fixes += swap_count

        report.dates_fixed = fixes
        if fixes > 0:
            report.operations.append(f"Fixed {fixes} date inconsistencies (swapped order/ship)")

        return df

    def _fix_negative_values(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """Fix negative values in columns that should be non-negative."""
        non_negative_cols = [
            "Product Price",
            "Order Item Quantity",
            "Days for shipping (real)",
            "Days for shipment (scheduled)",
            "Sales",
            "Order Item Product Price",
            "Order Item Total",
        ]

        total_fixed = 0
        for col in non_negative_cols:
            if col not in df.columns:
                continue
            if not pd.api.types.is_numeric_dtype(df[col]):
                continue

            neg_mask = df[col] < 0
            neg_count = int(neg_mask.sum())
            if neg_count > 0:
                df.loc[neg_mask, col] = df[col].abs()
                total_fixed += neg_count

        report.negatives_fixed = total_fixed
        if total_fixed > 0:
            report.operations.append(f"Fixed {total_fixed} negative values (converted to absolute)")

        return df

    def _normalize_categories(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """Normalize categorical columns to standard values."""
        normalized = 0

        # Shipping Mode
        if "Shipping Mode" in df.columns:
            df["Shipping Mode"] = df["Shipping Mode"].str.strip()
            invalid = ~df["Shipping Mode"].isin(self.VALID_SHIPPING_MODES)
            inv_count = int(invalid.sum())
            if inv_count > 0:
                df.loc[invalid, "Shipping Mode"] = "Standard Class"
                normalized += inv_count

        # Delivery Status
        if "Delivery Status" in df.columns:
            df["Delivery Status"] = df["Delivery Status"].str.strip()
            invalid = ~df["Delivery Status"].isin(self.VALID_DELIVERY_STATUS)
            inv_count = int(invalid.sum())
            if inv_count > 0:
                mode_val = df["Delivery Status"].mode().iloc[0]
                df.loc[invalid, "Delivery Status"] = mode_val
                normalized += inv_count

        # Market
        if "Market" in df.columns:
            df["Market"] = df["Market"].str.strip()

        # Customer Segment
        if "Customer Segment" in df.columns:
            df["Customer Segment"] = df["Customer Segment"].str.strip()
            invalid = ~df["Customer Segment"].isin(self.VALID_SEGMENTS)
            inv_count = int(invalid.sum())
            if inv_count > 0:
                df.loc[invalid, "Customer Segment"] = "Consumer"
                normalized += inv_count

        # General string columns: strip whitespace
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].str.strip()

        report.categories_normalized = normalized
        if normalized > 0:
            report.operations.append(f"Normalized {normalized} categorical values")

        return df

    def _validate_business_rules(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """Apply business rule corrections."""
        # Ensure Late_delivery_risk is binary integer
        if TARGET_COLUMN in df.columns:
            df[TARGET_COLUMN] = df[TARGET_COLUMN].astype(int).clip(0, 1)

        # Cap outlier shipping days at reasonable maximum (60 days)
        if "Days for shipping (real)" in df.columns:
            cap = 60
            over = int((df["Days for shipping (real)"] > cap).sum())
            if over > 0:
                df["Days for shipping (real)"] = df["Days for shipping (real)"].clip(upper=cap)
                report.operations.append(f"Capped {over} shipping days at {cap}")

        # Cap discount at 0.80
        if "Order Item Discount" in df.columns:
            df["Order Item Discount"] = df["Order Item Discount"].clip(0, 0.80)

        return df

    def _drop_invalid_rows(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """Drop rows that remain invalid after cleaning."""
        before = len(df)

        # Drop rows where critical columns are still null
        critical = ["Order Id", TARGET_COLUMN]
        existing_critical = [c for c in critical if c in df.columns]
        if existing_critical:
            df = df.dropna(subset=existing_critical)

        dropped = before - len(df)
        if dropped > 0:
            report.operations.append(f"Dropped {dropped} rows with null critical columns")

        return df.reset_index(drop=True)

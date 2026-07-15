"""
AMASCI Validation Service
===========================
Schema validation, data quality analysis, and validation reporting.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.core.constants import (
    MAX_NULL_RATIO_DATE,
    MAX_NULL_RATIO_REQUIRED,
    MAX_NULL_RATIO_TARGET,
    MIN_ROW_COUNT,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    TARGET_COLUMN,
)
from app.exceptions import (
    InsufficientDataException,
    SchemaValidationException,
)

logger = logging.getLogger(__name__)


@dataclass
class ColumnValidation:
    """Validation result for a single column."""

    name: str
    present: bool
    dtype: str = ""
    null_count: int = 0
    null_percent: float = 0.0
    unique_count: int = 0
    is_required: bool = False
    issues: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """Complete dataset validation report."""

    is_valid: bool = True
    quality_score: float = 0.0
    row_count: int = 0
    column_count: int = 0
    required_present: int = 0
    required_total: int = len(REQUIRED_COLUMNS)
    optional_present: int = 0
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    column_validations: list[ColumnValidation] = field(default_factory=list)
    duplicate_count: int = 0
    duplicate_percent: float = 0.0
    total_null_percent: float = 0.0
    date_issues: list[str] = field(default_factory=list)
    business_rule_violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to dictionary."""
        return {
            "is_valid": self.is_valid,
            "quality_score": round(self.quality_score, 4),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "schema": {
                "required_present": self.required_present,
                "required_total": self.required_total,
                "missing_required": self.missing_required,
                "missing_optional": self.missing_optional,
            },
            "duplicates": {
                "count": self.duplicate_count,
                "percent": round(self.duplicate_percent, 2),
            },
            "null_percent": round(self.total_null_percent, 2),
            "date_issues": self.date_issues,
            "business_rule_violations": self.business_rule_violations,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class ValidationService:
    """Validates uploaded datasets against schema and quality rules."""

    def validate(self, df: pd.DataFrame) -> ValidationReport:
        """
        Run complete validation pipeline.

        Steps:
        1. Row count check
        2. Schema validation (required/optional columns)
        3. Missing value analysis
        4. Duplicate detection
        5. Date validation
        6. Business rule validation
        7. Quality score computation
        """
        report = ValidationReport()
        report.row_count = len(df)
        report.column_count = len(df.columns)

        self._validate_row_count(df, report)
        if not report.is_valid:
            return report

        self._validate_schema(df, report)
        self._validate_missing_values(df, report)
        self._validate_duplicates(df, report)
        self._validate_dates(df, report)
        self._validate_business_rules(df, report)
        self._compute_quality_score(report)

        logger.info(
            f"Validation complete: valid={report.is_valid}, score={report.quality_score:.2f}",
            extra={"quality_score": report.quality_score},
        )

        return report

    def _validate_row_count(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Ensure minimum row count."""
        if len(df) < MIN_ROW_COUNT:
            report.is_valid = False
            report.errors.append(
                f"Insufficient rows: {len(df)}. Minimum required: {MIN_ROW_COUNT}"
            )

    def _validate_schema(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Check presence of required and optional columns."""
        columns_lower = {col.strip().lower(): col for col in df.columns}

        for req_col in REQUIRED_COLUMNS:
            if req_col.lower() in columns_lower:
                report.required_present += 1
            else:
                report.missing_required.append(req_col)

        for opt_col in OPTIONAL_COLUMNS:
            if opt_col.lower() in columns_lower:
                report.optional_present += 1
            else:
                report.missing_optional.append(opt_col)

        # Critical failure if too many required columns missing
        if report.missing_required:
            critical_missing = [
                c for c in report.missing_required
                if c in [TARGET_COLUMN, "Order Id", "order date (DateOrders)"]
            ]
            if critical_missing:
                report.is_valid = False
                report.errors.append(
                    f"Critical columns missing: {critical_missing}"
                )

    def _validate_missing_values(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Analyze missing values per column."""
        total_cells = df.shape[0] * df.shape[1]
        total_nulls = df.isnull().sum().sum()
        report.total_null_percent = (total_nulls / total_cells) * 100 if total_cells > 0 else 0

        for col in df.columns:
            null_count = int(df[col].isnull().sum())
            null_pct = (null_count / len(df)) * 100 if len(df) > 0 else 0
            is_required = col in REQUIRED_COLUMNS

            cv = ColumnValidation(
                name=col,
                present=True,
                dtype=str(df[col].dtype),
                null_count=null_count,
                null_percent=round(null_pct, 2),
                unique_count=int(df[col].nunique()),
                is_required=is_required,
            )

            if is_required and null_pct > MAX_NULL_RATIO_REQUIRED * 100:
                cv.issues.append(f"Null ratio {null_pct:.1f}% exceeds threshold")
                report.warnings.append(f"Column '{col}': {null_pct:.1f}% null values")

            if col == TARGET_COLUMN and null_count > 0:
                cv.issues.append("Target column has null values")
                report.errors.append("Target column 'Late_delivery_risk' contains nulls")
                report.is_valid = False

            report.column_validations.append(cv)

    def _validate_duplicates(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Detect duplicate rows."""
        dup_count = int(df.duplicated().sum())
        report.duplicate_count = dup_count
        report.duplicate_percent = (dup_count / len(df)) * 100 if len(df) > 0 else 0

        if report.duplicate_percent > 5.0:
            report.warnings.append(
                f"High duplicate rate: {report.duplicate_percent:.1f}%"
            )

    def _validate_dates(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Validate date columns for parseability and consistency."""
        date_columns = [
            "order date (DateOrders)",
            "shipping date (DateOrders)",
        ]

        for col in date_columns:
            if col not in df.columns:
                continue

            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                null_after_parse = int(parsed.isnull().sum())
                original_nulls = int(df[col].isnull().sum())
                unparseable = null_after_parse - original_nulls

                if unparseable > 0:
                    pct = (unparseable / len(df)) * 100
                    report.date_issues.append(
                        f"Column '{col}': {unparseable} unparseable dates ({pct:.1f}%)"
                    )
                    if pct > MAX_NULL_RATIO_DATE * 100:
                        report.warnings.append(f"Date column '{col}' has {pct:.1f}% parse failures")
            except Exception as e:
                report.date_issues.append(f"Column '{col}': parse error - {str(e)}")

        # Temporal consistency: shipping >= order
        if "order date (DateOrders)" in df.columns and "shipping date (DateOrders)" in df.columns:
            try:
                order_dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
                ship_dates = pd.to_datetime(df["shipping date (DateOrders)"], errors="coerce")
                mask = order_dates.notna() & ship_dates.notna()
                violations = int((ship_dates[mask] < order_dates[mask]).sum())
                if violations > 0:
                    report.date_issues.append(
                        f"Temporal inconsistency: {violations} records where ship_date < order_date"
                    )
            except Exception:
                pass

    def _validate_business_rules(self, df: pd.DataFrame, report: ValidationReport) -> None:
        """Validate domain-specific business rules."""
        # Rule 1: Product Price must be positive
        if "Product Price" in df.columns:
            neg_prices = int((df["Product Price"] < 0).sum())
            if neg_prices > 0:
                report.business_rule_violations.append(
                    f"Negative product prices: {neg_prices} records"
                )

        # Rule 2: Order Item Quantity must be positive
        if "Order Item Quantity" in df.columns:
            neg_qty = int((df["Order Item Quantity"] <= 0).sum())
            if neg_qty > 0:
                report.business_rule_violations.append(
                    f"Non-positive quantities: {neg_qty} records"
                )

        # Rule 3: Days for shipping must be non-negative
        if "Days for shipping (real)" in df.columns:
            neg_days = int((df["Days for shipping (real)"] < 0).sum())
            if neg_days > 0:
                report.business_rule_violations.append(
                    f"Negative shipping days: {neg_days} records"
                )

        # Rule 4: Late_delivery_risk must be binary
        if TARGET_COLUMN in df.columns:
            valid_values = df[TARGET_COLUMN].dropna().isin([0, 1])
            invalid = int((~valid_values).sum())
            if invalid > 0:
                report.business_rule_violations.append(
                    f"Non-binary target values: {invalid} records"
                )

        # Rule 5: Sales should be non-negative
        if "Sales" in df.columns:
            neg_sales = int((df["Sales"] < 0).sum())
            if neg_sales > 0:
                report.business_rule_violations.append(
                    f"Negative sales: {neg_sales} records"
                )

    def _compute_quality_score(self, report: ValidationReport) -> None:
        """
        Compute overall data quality score (0.0 - 1.0).

        Formula:
        score = 0.30 × completeness + 0.25 × schema_match + 0.20 × consistency
                + 0.15 × uniqueness + 0.10 × validity
        """
        # Completeness: inverse of null ratio
        completeness = 1.0 - (report.total_null_percent / 100.0)

        # Schema match: ratio of required columns present
        schema_match = report.required_present / report.required_total if report.required_total > 0 else 0

        # Consistency: inverse of date issues ratio
        date_issue_count = len(report.date_issues)
        consistency = max(0, 1.0 - (date_issue_count * 0.1))

        # Uniqueness: inverse of duplicate ratio
        uniqueness = 1.0 - (report.duplicate_percent / 100.0)

        # Validity: inverse of business rule violations
        violation_count = len(report.business_rule_violations)
        validity = max(0, 1.0 - (violation_count * 0.1))

        report.quality_score = (
            0.30 * completeness
            + 0.25 * schema_match
            + 0.20 * consistency
            + 0.15 * uniqueness
            + 0.10 * validity
        )

        report.quality_score = max(0.0, min(1.0, report.quality_score))

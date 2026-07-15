"""
AMASCI Data Profiling Service
================================
Generates comprehensive dataset statistics, distributions, and quality metrics.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ProfilingService:
    """Generates comprehensive data profiles for datasets."""

    def generate_profile(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Generate complete dataset profile.

        Includes:
        - Summary statistics
        - Per-column analysis
        - Missing value report
        - Duplicate report
        - Outlier report
        - Distribution summaries
        """
        profile = {
            "summary": self._generate_summary(df),
            "columns": self._profile_columns(df),
            "missing_values": self._missing_value_report(df),
            "duplicates": self._duplicate_report(df),
            "outliers": self._outlier_report(df),
            "correlations": self._top_correlations(df),
            "target_distribution": self._target_distribution(df),
        }

        logger.info(
            f"Profile generated: {len(df)} rows, {len(df.columns)} columns",
        )

        return profile

    def _generate_summary(self, df: pd.DataFrame) -> dict[str, Any]:
        """High-level dataset summary."""
        memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)

        return {
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_mb": round(memory_mb, 2),
            "numeric_columns": len(df.select_dtypes(include=[np.number]).columns),
            "categorical_columns": len(df.select_dtypes(include=["object"]).columns),
            "datetime_columns": len(df.select_dtypes(include=["datetime64"]).columns),
            "total_null_cells": int(df.isnull().sum().sum()),
            "total_null_percent": round(
                (df.isnull().sum().sum() / (df.shape[0] * df.shape[1])) * 100, 2
            ),
            "duplicate_rows": int(df.duplicated().sum()),
        }

    def _profile_columns(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Per-column profiling."""
        profiles = []

        for col in df.columns:
            col_profile: dict[str, Any] = {
                "name": col,
                "dtype": str(df[col].dtype),
                "null_count": int(df[col].isnull().sum()),
                "null_percent": round((df[col].isnull().sum() / len(df)) * 100, 2),
                "unique_count": int(df[col].nunique()),
                "unique_percent": round((df[col].nunique() / len(df)) * 100, 2),
            }

            if pd.api.types.is_numeric_dtype(df[col]):
                desc = df[col].describe()
                col_profile.update({
                    "mean": round(float(desc.get("mean", 0)), 4),
                    "std": round(float(desc.get("std", 0)), 4),
                    "min": float(desc.get("min", 0)),
                    "max": float(desc.get("max", 0)),
                    "q25": float(desc.get("25%", 0)),
                    "q50": float(desc.get("50%", 0)),
                    "q75": float(desc.get("75%", 0)),
                })
            elif df[col].dtype == "object":
                top_values = df[col].value_counts().head(5)
                col_profile["top_values"] = {
                    str(k): int(v) for k, v in top_values.items()
                }

            profiles.append(col_profile)

        return profiles

    def _missing_value_report(self, df: pd.DataFrame) -> dict[str, Any]:
        """Detailed missing value analysis."""
        null_counts = df.isnull().sum()
        null_cols = null_counts[null_counts > 0].sort_values(ascending=False)

        return {
            "total_missing_cells": int(null_counts.sum()),
            "columns_with_missing": len(null_cols),
            "columns_complete": len(df.columns) - len(null_cols),
            "details": [
                {
                    "column": col,
                    "missing_count": int(count),
                    "missing_percent": round((count / len(df)) * 100, 2),
                }
                for col, count in null_cols.items()
            ],
        }

    def _duplicate_report(self, df: pd.DataFrame) -> dict[str, Any]:
        """Duplicate row analysis."""
        dup_count = int(df.duplicated().sum())

        return {
            "total_duplicates": dup_count,
            "duplicate_percent": round((dup_count / len(df)) * 100, 2) if len(df) > 0 else 0,
            "unique_rows": len(df) - dup_count,
        }

    def _outlier_report(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Detect outliers using IQR method for numeric columns."""
        outlier_info = []
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) == 0:
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1

            if iqr == 0:
                continue

            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outlier_count = int(((series < lower) | (series > upper)).sum())

            if outlier_count > 0:
                outlier_info.append({
                    "column": col,
                    "outlier_count": outlier_count,
                    "outlier_percent": round((outlier_count / len(series)) * 100, 2),
                    "lower_bound": round(float(lower), 4),
                    "upper_bound": round(float(upper), 4),
                    "iqr": round(float(iqr), 4),
                })

        return sorted(outlier_info, key=lambda x: x["outlier_count"], reverse=True)

    def _top_correlations(self, df: pd.DataFrame, top_n: int = 10) -> list[dict[str, Any]]:
        """Find top correlated numeric column pairs."""
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.shape[1] < 2:
            return []

        corr_matrix = numeric_df.corr().abs()
        # Get upper triangle
        upper = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )

        pairs = []
        for col in upper.columns:
            for idx in upper.index:
                val = upper.loc[idx, col]
                if pd.notna(val) and val > 0.5:
                    pairs.append({
                        "column_1": idx,
                        "column_2": col,
                        "correlation": round(float(val), 4),
                    })

        return sorted(pairs, key=lambda x: x["correlation"], reverse=True)[:top_n]

    def _target_distribution(self, df: pd.DataFrame) -> dict[str, Any]:
        """Analyze target variable distribution."""
        from app.core.constants import TARGET_COLUMN

        if TARGET_COLUMN not in df.columns:
            return {"available": False}

        dist = df[TARGET_COLUMN].value_counts()
        total = len(df[TARGET_COLUMN].dropna())

        return {
            "available": True,
            "distribution": {str(k): int(v) for k, v in dist.items()},
            "balance_ratio": round(float(dist.min() / dist.max()), 4) if len(dist) > 1 else 1.0,
            "total_samples": total,
        }

"""
Tests for AMASCI Transformation Service
"""

import numpy as np
import pandas as pd
import pytest

from app.data_engineering.transformation import TransformationService


@pytest.fixture
def clean_df() -> pd.DataFrame:
    """Create a clean DataFrame ready for transformation."""
    n = 100
    return pd.DataFrame({
        "Order Id": range(1, n + 1),
        "order date (DateOrders)": pd.date_range("2023-01-01", periods=n, freq="D"),
        "shipping date (DateOrders)": pd.date_range("2023-01-04", periods=n, freq="D"),
        "Days for shipping (real)": np.random.randint(1, 10, n),
        "Days for shipment (scheduled)": np.random.randint(1, 7, n),
        "Late_delivery_risk": np.random.randint(0, 2, n),
        "Sales": np.random.uniform(10, 1000, n),
        "Order Profit Per Order": np.random.uniform(-50, 200, n),
        "Order Item Quantity": np.random.randint(1, 10, n),
        "Customer Email": ["test@test.com"] * n,
        "Customer Password": ["pass123"] * n,
    })


@pytest.fixture
def transformer() -> TransformationService:
    return TransformationService()


def test_date_features_extracted(transformer: TransformationService, clean_df: pd.DataFrame):
    """Date features should be extracted from order date."""
    df_t, report = transformer.transform(clean_df)
    assert "order_year" in df_t.columns
    assert "order_month" in df_t.columns
    assert "order_day" in df_t.columns
    assert "order_day_of_week" in df_t.columns
    assert "order_quarter" in df_t.columns
    assert "order_is_weekend" in df_t.columns


def test_delivery_duration_computed(transformer: TransformationService, clean_df: pd.DataFrame):
    """Delivery duration should be computed."""
    df_t, report = transformer.transform(clean_df)
    assert "delivery_duration_days" in df_t.columns
    assert (df_t["delivery_duration_days"] >= 0).all()


def test_period_columns_created(transformer: TransformationService, clean_df: pd.DataFrame):
    """Monthly and weekly period columns should be created."""
    df_t, report = transformer.transform(clean_df)
    assert "period_monthly" in df_t.columns
    assert "period_weekly" in df_t.columns


def test_unnecessary_columns_dropped(transformer: TransformationService, clean_df: pd.DataFrame):
    """PII and unnecessary columns should be removed."""
    df_t, report = transformer.transform(clean_df)
    assert "Customer Email" not in df_t.columns
    assert "Customer Password" not in df_t.columns


def test_sorted_by_date(transformer: TransformationService, clean_df: pd.DataFrame):
    """Output should be sorted by order date ascending."""
    df_t, report = transformer.transform(clean_df)
    dates = df_t["order date (DateOrders)"]
    assert dates.is_monotonic_increasing


def test_transformation_report(transformer: TransformationService, clean_df: pd.DataFrame):
    """Transformation should produce a report with added/removed columns."""
    df_t, report = transformer.transform(clean_df)
    assert len(report.columns_added) > 0
    assert len(report.columns_removed) > 0
    assert len(report.operations) > 0


def test_monthly_aggregation(transformer: TransformationService, clean_df: pd.DataFrame):
    """Monthly aggregation should produce valid metrics."""
    df_t, _ = transformer.transform(clean_df)
    monthly = transformer.create_monthly_aggregation(df_t)
    assert not monthly.empty
    assert "total_orders" in monthly.columns
    assert "late_delivery_rate" in monthly.columns
    assert (monthly["late_delivery_rate"] >= 0).all()
    assert (monthly["late_delivery_rate"] <= 1).all()


def test_weekly_aggregation(transformer: TransformationService, clean_df: pd.DataFrame):
    """Weekly aggregation should produce valid metrics."""
    df_t, _ = transformer.transform(clean_df)
    weekly = transformer.create_weekly_aggregation(df_t)
    assert not weekly.empty
    assert "total_orders" in weekly.columns

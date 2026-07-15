"""
Tests for AMASCI Cleaning Service
"""

import numpy as np
import pandas as pd
import pytest

from app.data_engineering.cleaning import CleaningService


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a sample DataFrame with known issues."""
    return pd.DataFrame({
        "Order Id": [1, 2, 3, 4, 5, 5, 6, 7, 8, 9],
        "Late_delivery_risk": [0, 1, 0, 1, 0, 0, 1, None, 0, 1],
        "Product Price": [10.0, 20.0, -5.0, 30.0, 40.0, 40.0, 50.0, 60.0, 70.0, 80.0],
        "Order Item Quantity": [1, 2, 3, -1, 5, 5, 6, 7, 8, 9],
        "Days for shipping (real)": [3, 5, 2, 7, 4, 4, 6, 8, 1, 3],
        "Shipping Mode": ["Standard Class", "First Class", " Same Day ", "Invalid", "Second Class",
                          "Second Class", "Standard Class", "First Class", "Same Day", "Standard Class"],
        "Customer Segment": ["Consumer", "Corporate", "Home Office", "Invalid", "Consumer",
                             "Consumer", "Corporate", "Home Office", "Consumer", "Corporate"],
        "Sales": [100, 200, 300, 400, 500, 500, 600, 700, 800, 900],
        "Order Item Discount": [0.1, 0.2, 0.3, 0.9, 0.5, 0.5, 0.1, 0.2, 0.3, 0.4],
    })


@pytest.fixture
def cleaner() -> CleaningService:
    return CleaningService()


def test_duplicates_removed(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Exact duplicate rows should be removed."""
    df_clean, report = cleaner.clean(sample_df)
    assert report.duplicates_removed >= 1


def test_null_target_rows_dropped(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Rows with null target should be dropped."""
    df_clean, report = cleaner.clean(sample_df)
    assert df_clean["Late_delivery_risk"].isnull().sum() == 0


def test_negative_prices_fixed(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Negative prices should be converted to absolute values."""
    df_clean, report = cleaner.clean(sample_df)
    assert (df_clean["Product Price"] >= 0).all()


def test_negative_quantities_fixed(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Negative quantities should be fixed."""
    df_clean, report = cleaner.clean(sample_df)
    assert (df_clean["Order Item Quantity"] >= 0).all()


def test_shipping_mode_normalized(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Invalid shipping modes should be normalized."""
    df_clean, report = cleaner.clean(sample_df)
    valid_modes = {"Standard Class", "First Class", "Second Class", "Same Day"}
    assert set(df_clean["Shipping Mode"].unique()).issubset(valid_modes)


def test_discount_capped(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Discounts should be capped at 0.80."""
    df_clean, report = cleaner.clean(sample_df)
    assert (df_clean["Order Item Discount"] <= 0.80).all()


def test_cleaning_report_generated(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Cleaning should produce a complete report."""
    df_clean, report = cleaner.clean(sample_df)
    assert report.rows_before > 0
    assert report.rows_after > 0
    assert report.rows_after <= report.rows_before
    assert len(report.operations) > 0


def test_target_is_binary(cleaner: CleaningService, sample_df: pd.DataFrame):
    """Target column should only contain 0 and 1."""
    df_clean, report = cleaner.clean(sample_df)
    assert set(df_clean["Late_delivery_risk"].unique()).issubset({0, 1})

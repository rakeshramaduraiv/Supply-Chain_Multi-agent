"""
Tests for AMASCI Validation Service
"""

import numpy as np
import pandas as pd
import pytest

from app.data_engineering.validation import ValidationService, ValidationReport


@pytest.fixture
def valid_dataframe() -> pd.DataFrame:
    """Create a valid test DataFrame matching DataCo schema."""
    n = 1500
    return pd.DataFrame({
        "Order Id": range(1, n + 1),
        "order date (DateOrders)": pd.date_range("2023-01-01", periods=n, freq="h"),
        "shipping date (DateOrders)": pd.date_range("2023-01-03", periods=n, freq="h"),
        "Days for shipping (real)": np.random.randint(1, 10, n),
        "Days for shipment (scheduled)": np.random.randint(1, 7, n),
        "Late_delivery_risk": np.random.randint(0, 2, n),
        "Delivery Status": np.random.choice(
            ["Late delivery", "Advance shipping", "Shipping on time"], n
        ),
        "Shipping Mode": np.random.choice(
            ["Standard Class", "First Class", "Second Class", "Same Day"], n
        ),
        "Category Name": np.random.choice(["Electronics", "Furniture", "Clothing"], n),
        "Product Name": [f"Product_{i}" for i in range(n)],
        "Product Price": np.random.uniform(10, 500, n),
        "Order Region": np.random.choice(["West", "East", "Central", "South"], n),
        "Order Country": np.random.choice(["USA", "UK", "Germany"], n),
        "Order City": np.random.choice(["New York", "London", "Berlin"], n),
        "Market": np.random.choice(["USCA", "Europe", "Pacific Asia"], n),
        "Customer Id": np.random.randint(1000, 9999, n),
        "Customer Segment": np.random.choice(["Consumer", "Corporate", "Home Office"], n),
        "Order Item Quantity": np.random.randint(1, 10, n),
        "Sales": np.random.uniform(10, 1000, n),
        "Order Profit Per Order": np.random.uniform(-50, 200, n),
        "Order Item Discount": np.random.uniform(0, 0.5, n),
        "Order Item Product Price": np.random.uniform(10, 500, n),
        "Order Item Total": np.random.uniform(10, 1000, n),
        "Benefit per order": np.random.uniform(0, 100, n),
        "Sales per customer": np.random.uniform(100, 5000, n),
        "Department Name": np.random.choice(["Technology", "Office Supplies"], n),
        "Latitude": np.random.uniform(25, 50, n),
        "Longitude": np.random.uniform(-120, -70, n),
    })


@pytest.fixture
def validator() -> ValidationService:
    return ValidationService()


def test_valid_dataset_passes(validator: ValidationService, valid_dataframe: pd.DataFrame):
    """A properly formed dataset should pass validation."""
    report = validator.validate(valid_dataframe)
    assert report.is_valid is True
    assert report.quality_score > 0.7


def test_insufficient_rows_fails(validator: ValidationService):
    """Dataset with too few rows should fail."""
    df = pd.DataFrame({"Order Id": range(10), "Late_delivery_risk": [0] * 10})
    report = validator.validate(df)
    assert report.is_valid is False
    assert any("Insufficient" in e for e in report.errors)


def test_missing_target_column_fails(validator: ValidationService, valid_dataframe: pd.DataFrame):
    """Missing target column should fail validation."""
    df = valid_dataframe.drop(columns=["Late_delivery_risk"])
    report = validator.validate(df)
    assert report.is_valid is False


def test_null_target_fails(validator: ValidationService, valid_dataframe: pd.DataFrame):
    """Null values in target column should fail."""
    df = valid_dataframe.copy()
    df.loc[0:5, "Late_delivery_risk"] = None
    report = validator.validate(df)
    assert report.is_valid is False


def test_duplicates_detected(validator: ValidationService, valid_dataframe: pd.DataFrame):
    """Duplicates should be detected and reported."""
    df = pd.concat([valid_dataframe, valid_dataframe.head(100)], ignore_index=True)
    report = validator.validate(df)
    assert report.duplicate_count >= 100


def test_quality_score_range(validator: ValidationService, valid_dataframe: pd.DataFrame):
    """Quality score should be between 0 and 1."""
    report = validator.validate(valid_dataframe)
    assert 0.0 <= report.quality_score <= 1.0


def test_negative_prices_flagged(validator: ValidationService, valid_dataframe: pd.DataFrame):
    """Negative product prices should be flagged as business rule violation."""
    df = valid_dataframe.copy()
    df.loc[0:10, "Product Price"] = -50.0
    report = validator.validate(df)
    assert any("Negative product prices" in v for v in report.business_rule_violations)

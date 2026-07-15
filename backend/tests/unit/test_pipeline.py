"""
Tests for AMASCI Data Engineering Pipeline
"""

import numpy as np
import pandas as pd
import pytest

from app.data_engineering.pipeline import DataEngineeringPipeline


@pytest.fixture
def full_dataframe() -> pd.DataFrame:
    """Create a full test DataFrame matching DataCo schema."""
    n = 2000
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
        "Category Name": np.random.choice(["Electronics", "Furniture"], n),
        "Product Name": [f"Product_{i}" for i in range(n)],
        "Product Price": np.random.uniform(10, 500, n),
        "Order Region": np.random.choice(["West", "East"], n),
        "Order Country": np.random.choice(["USA", "UK"], n),
        "Order City": np.random.choice(["New York", "London"], n),
        "Market": np.random.choice(["USCA", "Europe"], n),
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


def test_pipeline_completes_successfully(full_dataframe: pd.DataFrame):
    """Full pipeline should complete without errors."""
    pipeline = DataEngineeringPipeline()
    df_result, result = pipeline.execute(full_dataframe, "test-dataset-001")
    assert result.status == "completed"
    assert result.row_count_final > 0
    assert result.total_duration_ms > 0


def test_pipeline_produces_validation_report(full_dataframe: pd.DataFrame):
    """Pipeline should produce a validation report."""
    pipeline = DataEngineeringPipeline()
    _, result = pipeline.execute(full_dataframe, "test-002")
    assert result.validation_report is not None
    assert "quality_score" in result.validation_report


def test_pipeline_produces_cleaning_report(full_dataframe: pd.DataFrame):
    """Pipeline should produce a cleaning report."""
    pipeline = DataEngineeringPipeline()
    _, result = pipeline.execute(full_dataframe, "test-003")
    assert result.cleaning_report is not None
    assert "rows_before" in result.cleaning_report


def test_pipeline_produces_profile(full_dataframe: pd.DataFrame):
    """Pipeline should produce a dataset profile."""
    pipeline = DataEngineeringPipeline()
    _, result = pipeline.execute(full_dataframe, "test-004")
    assert result.profile is not None
    assert "summary" in result.profile


def test_pipeline_adds_date_features(full_dataframe: pd.DataFrame):
    """Pipeline output should contain extracted date features."""
    pipeline = DataEngineeringPipeline()
    df_result, _ = pipeline.execute(full_dataframe, "test-005")
    assert "order_year" in df_result.columns
    assert "order_month" in df_result.columns
    assert "period_monthly" in df_result.columns


def test_pipeline_fails_on_insufficient_data():
    """Pipeline should fail on datasets with too few rows."""
    df = pd.DataFrame({"Order Id": [1, 2, 3], "Late_delivery_risk": [0, 1, 0]})
    pipeline = DataEngineeringPipeline()
    _, result = pipeline.execute(df, "test-fail")
    assert result.status == "failed"


def test_pipeline_result_serializable(full_dataframe: pd.DataFrame):
    """Pipeline result should be serializable to dict."""
    pipeline = DataEngineeringPipeline()
    _, result = pipeline.execute(full_dataframe, "test-006")
    result_dict = result.to_dict()
    assert isinstance(result_dict, dict)
    assert "dataset_id" in result_dict
    assert "status" in result_dict

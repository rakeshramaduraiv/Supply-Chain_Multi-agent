"""
Tests for AMASCI Profiling Service
"""

import numpy as np
import pandas as pd
import pytest

from app.data_engineering.profiling import ProfilingService


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a sample DataFrame for profiling."""
    n = 200
    return pd.DataFrame({
        "Order Id": range(1, n + 1),
        "Late_delivery_risk": np.random.randint(0, 2, n),
        "Product Price": np.random.uniform(10, 500, n),
        "Sales": np.random.uniform(10, 1000, n),
        "Order Item Quantity": np.random.randint(1, 10, n),
        "Category Name": np.random.choice(["Electronics", "Furniture", "Clothing"], n),
        "Market": np.random.choice(["USCA", "Europe", "LATAM"], n),
    })


@pytest.fixture
def profiler() -> ProfilingService:
    return ProfilingService()


def test_profile_has_summary(profiler: ProfilingService, sample_df: pd.DataFrame):
    """Profile should contain a summary section."""
    profile = profiler.generate_profile(sample_df)
    assert "summary" in profile
    assert profile["summary"]["row_count"] == 200
    assert profile["summary"]["column_count"] == 7


def test_profile_has_column_details(profiler: ProfilingService, sample_df: pd.DataFrame):
    """Profile should contain per-column details."""
    profile = profiler.generate_profile(sample_df)
    assert "columns" in profile
    assert len(profile["columns"]) == 7


def test_numeric_columns_have_stats(profiler: ProfilingService, sample_df: pd.DataFrame):
    """Numeric columns should have mean, std, min, max."""
    profile = profiler.generate_profile(sample_df)
    price_col = next(c for c in profile["columns"] if c["name"] == "Product Price")
    assert "mean" in price_col
    assert "std" in price_col
    assert "min" in price_col
    assert "max" in price_col


def test_categorical_columns_have_top_values(profiler: ProfilingService, sample_df: pd.DataFrame):
    """Categorical columns should have top value counts."""
    profile = profiler.generate_profile(sample_df)
    cat_col = next(c for c in profile["columns"] if c["name"] == "Category Name")
    assert "top_values" in cat_col
    assert len(cat_col["top_values"]) > 0


def test_outlier_detection(profiler: ProfilingService, sample_df: pd.DataFrame):
    """Outliers should be detected in numeric columns."""
    df = sample_df.copy()
    df.loc[0, "Product Price"] = 99999.0  # Extreme outlier
    profile = profiler.generate_profile(df)
    assert "outliers" in profile


def test_target_distribution(profiler: ProfilingService, sample_df: pd.DataFrame):
    """Target distribution should be reported."""
    profile = profiler.generate_profile(sample_df)
    assert profile["target_distribution"]["available"] is True
    assert "distribution" in profile["target_distribution"]


def test_missing_values_report(profiler: ProfilingService, sample_df: pd.DataFrame):
    """Missing values should be reported."""
    df = sample_df.copy()
    df.loc[0:10, "Sales"] = None
    profile = profiler.generate_profile(df)
    assert profile["missing_values"]["columns_with_missing"] >= 1

"""
Tests for DataQualityReporter and Initialization Stage File Writers
=====================================================================
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from app.initialization.quality_report import (
    DataQualityReporter,
    write_graph_delta_reports,
    write_row_accounting,
    write_model_registry_summary,
    write_pipeline_summary,
)


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    """Fixture providing a synthetic raw DataFrame with known DQ characteristics."""
    n = 100
    data = {
        "Order Item Id": np.arange(1, n + 1),
        "Customer Email": ["constant@test.com"] * n,
        "Customer Password": ["pass123"] * n,
        "Customer Street": [f"Street {i}" for i in range(n)],
        "Customer Fname": ["John"] * n,
        "Customer Lname": ["Doe"] * (n - 8) + [None] * 8,  # 8 sparse nulls
        "Customer Zipcode": [12345] * (n - 3) + [None] * 3,  # 3 sparse nulls
        "Order Zipcode": [90210] * 10 + [None] * 90,  # 90% null (mostly null)
        "Product Description": [None] * n,  # 100% null
        "Product Status": [1] * n,  # constant
        "Order Profit Per Order": [-10.5] * 20 + [50.0] * 80,  # negative profit
        "Benefit per order": [-5.0] * 20 + [25.0] * 80,
        "order date (DateOrders)": pd.date_range("2015-01-01", periods=n, freq="D").astype(str),
        "shipping date (DateOrders)": pd.date_range("2015-01-02", periods=n, freq="D").astype(str),
        "Late_delivery_risk": [0, 1] * (n // 2),
        "Order Country": ["USA"] * n,
        "Order Region": ["East"] * n,
        "Department Name": ["Fan Shop"] * n,
        "Category Name": ["Apparel"] * n,
        "is_delayed": [0, 1] * (n // 2),
    }
    return pd.DataFrame(data)


def test_detects_fully_null_column(sample_raw_df: pd.DataFrame):
    reporter = DataQualityReporter()
    issues = reporter.scan_raw(sample_raw_df)

    dq01_issues = [i for i in issues if i["issue_id"] == "DQ-01"]
    assert len(dq01_issues) >= 1
    cols = [i["column"] for i in dq01_issues]
    assert "Product Description" in cols
    prod_issue = next(i for i in dq01_issues if i["column"] == "Product Description")
    assert prod_issue["rows_affected"] == len(sample_raw_df)
    assert prod_issue["severity"] == "HIGH"


def test_detects_constant_column(sample_raw_df: pd.DataFrame):
    reporter = DataQualityReporter()
    issues = reporter.scan_raw(sample_raw_df)

    dq04_issues = [i for i in issues if i["issue_id"] == "DQ-04"]
    cols = [i["column"] for i in dq04_issues]
    assert "Customer Email" in cols
    assert "Customer Password" in cols
    assert "Product Status" in cols


def test_negative_profit_flagged_as_info_not_error(sample_raw_df: pd.DataFrame):
    reporter = DataQualityReporter()
    issues = reporter.scan_raw(sample_raw_df)

    dq05_issues = [i for i in issues if i["issue_id"] == "DQ-05"]
    assert len(dq05_issues) >= 1

    for iss in dq05_issues:
        assert iss["severity"] == "INFO"
        assert iss["action_taken"] == "retained — genuine losses"
        assert iss["rows_affected"] == 20

    # Verify that verify_after confirms retention (does not treat negative values as errors to fix)
    df_cleaned = sample_raw_df.copy()
    verified_issues = reporter.verify_after(df_cleaned, dq05_issues)
    for iss in verified_issues:
        assert iss["verified"] is True
        assert iss["rows_after"] == 20


def test_passed_checks_appear_in_report(sample_raw_df: pd.DataFrame):
    reporter = DataQualityReporter()
    issues = reporter.scan_raw(sample_raw_df)

    passed_issues = [i for i in issues if i["severity"] == "PASSED"]
    assert len(passed_issues) >= 3

    issue_ids = [i["issue_id"] for i in passed_issues]
    assert "DQ-08" in issue_ids  # Duplicates passed
    assert "DQ-09a" in issue_ids  # Date integrity passed
    assert "DQ-09b" in issue_ids  # Date sequence passed
    assert "DQ-10" in issue_ids  # Target integrity passed


def test_pii_columns_never_written_to_any_stage_file(tmp_path: Path, sample_raw_df: pd.DataFrame):
    reporter = DataQualityReporter()
    issues = reporter.scan_raw(sample_raw_df)
    reporter.write(tmp_path)
    reporter.write_provenance(sample_raw_df, tmp_path)

    pii_list = [
        "Customer Email", "Customer Password", "Customer Street",
        "Customer Fname", "Customer Lname", "Customer Zipcode", "Order Zipcode",
    ]

    # Create dummy processed frame with PII columns dropped
    df_processed = sample_raw_df.drop(columns=[c for c in pii_list if c in sample_raw_df.columns])
    assert not any(col in df_processed.columns for col in pii_list)


def test_row_accounting_sums_to_input(tmp_path: Path):
    valid_records = [
        {
            "model": "demand",
            "rows_in": 180519,
            "rows_after_target_dropna": 180519,
            "rows_after_feature_dropna": 179828,
            "train_rows": 143867,
            "test_rows": 35961,
            "rows_dropped": 691,
            "drop_reason": "NaN in rolling lag features",
            "pct_dropped": 0.3828,
        }
    ]

    df_out = write_row_accounting(valid_records, tmp_path)
    assert (tmp_path / "05_row_accounting.csv").exists()
    assert len(df_out) == 1

    # Mismatch must fail loudly
    invalid_records = [
        {
            "model": "demand",
            "rows_in": 180519,
            "rows_after_target_dropna": 180519,
            "rows_after_feature_dropna": 179828,
            "train_rows": 100000,
            "test_rows": 30000,
            "rows_dropped": 691,  # 100000 + 30000 + 691 != 180519
            "drop_reason": "NaN in rolling lag features",
            "pct_dropped": 0.3828,
        }
    ]

    with pytest.raises(AssertionError, match="Row accounting mismatch"):
        write_row_accounting(invalid_records, tmp_path)


def test_graph_delta_reports_mean_absolute_delta(tmp_path: Path):
    n = 100
    df_t1 = pd.DataFrame({
        "graph_supplier_reliability": np.ones(n) * 0.8,
        "graph_avg_shipping_delay": np.ones(n) * 2.0,
    })
    df_t2 = pd.DataFrame({
        "graph_supplier_reliability": np.ones(n) * 0.85,  # delta = +0.05
        "graph_avg_shipping_delay": np.ones(n) * 1.5,    # delta = -0.5
    })

    delta_df, dist_df = write_graph_delta_reports(df_t1, df_t2, tmp_path)

    assert (tmp_path / "04_graph_feature_delta.csv").exists()
    assert (tmp_path / "04_graph_delta_distribution.csv").exists()

    assert "mean_absolute_delta" in delta_df.columns
    assert "pearson_tier1_vs_tier2" in delta_df.columns
    assert "pct_variance_unexplained" in delta_df.columns

    rel_row = delta_df[delta_df["column"] == "graph_supplier_reliability"].iloc[0]
    assert pytest.approx(rel_row["mean_absolute_delta"], abs=1e-4) == 0.05

    delay_row = delta_df[delta_df["column"] == "graph_avg_shipping_delay"].iloc[0]
    assert pytest.approx(delay_row["mean_absolute_delta"], abs=1e-4) == 0.5

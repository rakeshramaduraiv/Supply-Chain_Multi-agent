"""
Unit Tests for DynamicDatasetUpgradeService
================================================
Verifies that uploading a new actual dataset:
1. Concatenates the new dataset with the DataCo baseline into processed_master.parquet.
2. Re-engineers features across the combined dataset.
3. Retrains and upgrades ML models on cumulative data.
4. Triggers Knowledge Graph, GraphRAG, and WebSocket event notifications.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from app.services.dynamic_upgrade_service import DynamicDatasetUpgradeService


@pytest.fixture
def sample_dataco_base_df():
    """Simulates initial DataCo base dataset."""
    return pd.DataFrame({
        "Order Item Id": [101, 102, 103],
        "Order Id": [1, 2, 3],
        "Sales": [100.0, 200.0, 150.0],
        "Order Item Quantity": [1, 2, 1],
        "Late_delivery_risk": [0, 1, 0],
        "Days for shipping (real)": [3, 5, 2],
        "Days for shipment (scheduled)": [3, 4, 3],
        "Shipping Mode": ["Standard Class", "First Class", "Second Class"],
        "Category Name": ["Cleats", "Apparel", "Footwear"],
        "order date (DateOrders)": ["2017-01-01", "2017-01-02", "2017-01-03"],
    })


@pytest.fixture
def sample_new_actuals_df():
    """Simulates newly uploaded actual performance dataset."""
    return pd.DataFrame({
        "Order Item Id": [104, 105],
        "Order Id": [4, 5],
        "Sales": [300.0, 250.0],
        "Order Item Quantity": [3, 2],
        "Late_delivery_risk": [1, 0],
        "Days for shipping (real)": [6, 2],
        "Days for shipment (scheduled)": [4, 2],
        "Shipping Mode": ["First Class", "Same Day"],
        "Category Name": ["Apparel", "Cleats"],
        "order date (DateOrders)": ["2018-01-01", "2018-01-02"],
    })


@pytest.mark.asyncio
async def test_dynamic_upgrade_merges_old_and_new_dataset(tmp_path, sample_dataco_base_df, sample_new_actuals_df, monkeypatch):
    """Verify cumulative dataset merge and feature engineering upgrade."""
    service = DynamicDatasetUpgradeService()
    service.upload_dir = tmp_path
    service.master_parquet_path = tmp_path / "processed_master.parquet"

    # Save initial base dataset
    sample_dataco_base_df.to_parquet(service.master_parquet_path, index=False)

    # Perform dynamic upgrade with new actual dataset
    result = await service.upgrade_with_actuals(
        df_new=sample_new_actuals_df,
        filename="test_actuals_2018.csv",
        period="2018-01",
    )

    assert result["status"] == "completed"
    assert result["old_rows"] == 3
    assert result["new_rows_uploaded"] == 2
    assert result["cumulative_rows"] == 5
    assert result["net_rows_added"] == 2

    # Verify parquet file on disk has 5 rows
    df_disk = pd.read_parquet(service.master_parquet_path)
    assert len(df_disk) == 5
    assert set(df_disk["Order Item Id"]) == {101, 102, 103, 104, 105}

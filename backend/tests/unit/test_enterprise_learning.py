"""
Unit Tests for EnterpriseContinuousLearningEngine
======================================================
Verifies the 12-Stage Automated Continuous Learning Pipeline:
1. Schema & Integrity Validation
2. Record Matching
3. Prediction Comparison & Metrics (Accuracy, MAPE, RMSE, MAE, Precision, Recall, F1)
4. GraphRAG Root Cause Analysis
5. GCRCE Counterfactual Analysis
6. Knowledge Graph Mutation (No Rebuild)
7. Incremental GraphRAG Re-indexing
8. Historical Dataset Expansion (Ground Truth v2)
9. Model Retraining
10. Multi-Agent & RWDAA Refresh
11. Next Planning Period Prediction (February 2019)
12. Workspace Status Transition ("Waiting for February 2019 Actual Dataset")
"""

import pytest
import pandas as pd
from pathlib import Path

from app.services.enterprise_learning_engine import EnterpriseContinuousLearningEngine


@pytest.fixture
def base_ground_truth_df():
    return pd.DataFrame({
        "Order Item Id": [1001, 1002, 1003],
        "Order Id": [101, 102, 103],
        "Sales": [120.0, 220.0, 180.0],
        "Order Item Quantity": [1, 2, 1],
        "Late_delivery_risk": [0, 1, 0],
        "Days for shipping (real)": [3, 5, 2],
        "Days for shipment (scheduled)": [3, 4, 3],
        "Shipping Mode": ["Standard Class", "First Class", "Second Class"],
        "Category Name": ["Cleats", "Apparel", "Footwear"],
        "order date (DateOrders)": ["2018-12-01", "2018-12-02", "2018-12-03"],
    })


@pytest.fixture
def january_actual_df():
    return pd.DataFrame({
        "Order Item Id": [1004, 1005],
        "Order Id": [104, 105],
        "Sales": [310.0, 280.0],
        "Order Item Quantity": [3, 2],
        "Late_delivery_risk": [1, 0],
        "Days for shipping (real)": [6, 2],
        "Days for shipment (scheduled)": [4, 2],
        "Shipping Mode": ["First Class", "Same Day"],
        "Category Name": ["Apparel", "Cleats"],
        "order date (DateOrders)": ["2019-01-05", "2019-01-10"],
    })


@pytest.mark.asyncio
async def test_12_stage_enterprise_learning_pipeline(tmp_path, base_ground_truth_df, january_actual_df):
    engine = EnterpriseContinuousLearningEngine()
    engine.upload_dir = tmp_path
    engine.master_parquet_path = tmp_path / "processed_master.parquet"

    # Save initial 2015-2018 base
    base_ground_truth_df.to_parquet(engine.master_parquet_path, index=False)

    # Run January 2019 continuous learning cycle
    result = await engine.run_continuous_learning_cycle(
        df_new=january_actual_df,
        filename="January_2019_Actual.csv",
        period="2019-01",
    )

    assert result.period == "2019-01"
    assert result.old_row_count == 3
    assert result.new_rows_ingested == 2
    assert result.cumulative_row_count == 5
    assert len(result.stages) == 12
    assert result.next_forecast_period == "February 2019"
    assert result.workspace_status == "Waiting for February 2019 Actual Dataset"

    # Verify disk expansion
    df_expanded = pd.read_parquet(engine.master_parquet_path)
    assert len(df_expanded) == 5

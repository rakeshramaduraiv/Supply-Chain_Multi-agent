"""
tests/critical/test_stage3_requires_forecast.py
------------------------------------------------
Verifies that Stage 3 is skipped and returns None metrics when no forecast exists.
"""

import pandas as pd
import pytest
from app.services.cycle_service import _stage3_compute_metrics, StageResult

def test_stage3_skipped_when_no_forecast():
    # Call _stage3_compute_metrics with forecast_exists=False
    df_matched = pd.DataFrame({"Order Item Quantity": [1, 2], "qty_roll_7": [1, 2]})
    s3, metrics = _stage3_compute_metrics(df_matched, forecast_exists=False, period="2018-02")
    
    assert s3.status == "SKIPPED"
    assert "no standing forecast" in s3.detail.get("reason", "")
    assert metrics is None

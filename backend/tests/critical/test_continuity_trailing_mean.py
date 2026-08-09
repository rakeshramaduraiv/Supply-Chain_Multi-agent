"""
tests/critical/test_continuity_trailing_mean.py
------------------------------------------------
Verifies that the row count and late rate warning calculations in validate_continuity
use the trailing 6 months, not the total/n_periods.
"""

import pandas as pd
import pytest
from app.ingestion.continuity import validate_continuity, ContinuityReport

def test_trailing_mean_row_count():
    # Build a cumulative dataset spanning 12 months.
    # The first 6 months have 10,000 rows each.
    # The last 6 months have 2,000 rows each.
    # The new upload has 2,100 rows.
    # If it is a true trailing 6-month mean, the mean of the last 6 months is 2,000.
    # The deviation of 2,100 from 2,000 is 5% (well below the 50% warning threshold).
    # If it were the global mean (6000), the deviation would be (6000-2100)/6000 = 65% (triggering warning).
    
    rows = []
    # 12 months before 2018-02-01
    months = [
        (2017, 2), (2017, 3), (2017, 4), (2017, 5), (2017, 6), (2017, 7),
        (2017, 8), (2017, 9), (2017, 10), (2017, 11), (2017, 12), (2018, 1)
    ]
    
    for idx, (y, m) in enumerate(months):
        # First 6 months (idx 0 to 5): 10,000 rows each.
        # Last 6 months (idx 6 to 11): 2,000 rows each.
        count = 10000 if idx < 6 else 2000
        for i in range(count):
            rows.append({
                "order_date": f"{y}-{m:02d}-01",
                "target": 0,
                "order_item_id": f"cum_{idx}_{i}"
            })
            
    cumulative_df = pd.DataFrame(rows)
    
    # New upload has 2100 rows for 2018-02
    new_rows = []
    for i in range(2100):
        new_rows.append({
            "order_date": "2018-02-01",
            "target": 0,
            "order_item_id": f"new_{i}"
        })
    new_df = pd.DataFrame(new_rows)
    
    report = validate_continuity(new_df, cumulative_df, claimed_period="2018-02")
    
    # Check that NO warning of DRIFT_ROW_COUNT is raised
    row_count_warnings = [w for w in report.warnings if "DRIFT_ROW_COUNT" in w]
    assert not row_count_warnings, f"Expected no row count warning, but got: {row_count_warnings}"

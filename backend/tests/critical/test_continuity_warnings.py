"""
tests/critical/test_continuity_warnings.py
-------------------------------------------
Verifies that uploading 2018-04.csv (declared supplier_degradation 0.18 in
data/continuation/manifests/2018-04.json) produces at least one continuity
warning in the CycleResult.

The test is unit-level: it calls validate_continuity() directly with a
synthetic cumulative frame whose trailing late rate is far from the 2018-04
late rate, triggering the DRIFT_LATE_RATE warn path.
"""

import pandas as pd
import pytest

from app.ingestion.continuity import validate_continuity, ContinuityReport


def _make_cumulative(n_months: int = 6, base_late_rate: float = 0.40) -> pd.DataFrame:
    """Build a synthetic cumulative frame ending in March 2018 (contiguous with 2018-04).

    Introduces slight month-to-month variation so trailing std > 0, which is
    required for the DRIFT_LATE_RATE warn path to fire.
    """
    rows = []
    # 6 months ending 2018-03 so gap to 2018-04-01 is 1 day
    months = [(2017, 10), (2017, 11), (2017, 12), (2018, 1), (2018, 2), (2018, 3)]
    # Vary late rate slightly per month: 0.38, 0.40, 0.39, 0.41, 0.40, 0.42
    rates = [0.38, 0.40, 0.39, 0.41, 0.40, 0.42]
    for idx, (y, m) in enumerate(months[:n_months]):
        rate = rates[idx]
        for d in range(1, 29):
            rows.append({
                "order_date": f"{y}-{m:02d}-{d:02d}",
                "target": 1 if d <= int(28 * rate) else 0,
                "order_item_id": f"cum_{idx}_{d}",
            })
    return pd.DataFrame(rows)


def _make_new_df(late_rate: float = 0.58, period: str = "2018-04") -> pd.DataFrame:
    """Build a synthetic new upload with elevated late rate (supplier_degradation)."""
    rows = []
    for d in range(1, 29):
        rows.append({
            "order_date": f"{period}-{d:02d}",
            "target": 1 if d <= int(28 * late_rate) else 0,
            "order_item_id": f"new_{d}",
        })
    return pd.DataFrame(rows)


def test_supplier_degradation_produces_continuity_warning():
    """
    2018-04 has declared supplier_degradation 0.18.
    Simulated as late_rate=0.58 vs trailing mean ~0.40 (std ~0.01).
    Deviation >> 3 sigma -> DRIFT_LATE_RATE warning must be present.
    """
    cumulative = _make_cumulative(n_months=6, base_late_rate=0.40)
    new_df = _make_new_df(late_rate=0.58, period="2018-04")

    report: ContinuityReport = validate_continuity(
        new_df, cumulative, claimed_period="2018-04"
    )

    assert report.ok, "Report should be ok=True (warnings do not reject)"
    assert len(report.warnings) >= 1, (
        f"Expected at least one continuity warning for supplier_degradation period, "
        f"got: {report.warnings}"
    )
    drift_warnings = [w for w in report.warnings if "DRIFT_LATE_RATE" in w]
    assert drift_warnings, (
        f"Expected a DRIFT_LATE_RATE warning, got: {report.warnings}"
    )


def test_normal_period_no_warnings():
    """A period with late rate matching the trailing mean produces no warnings."""
    cumulative = _make_cumulative(n_months=6, base_late_rate=0.40)
    new_df = _make_new_df(late_rate=0.40, period="2018-04")

    report = validate_continuity(new_df, cumulative, claimed_period="2018-04")

    assert report.ok
    drift_warnings = [w for w in report.warnings if "DRIFT_LATE_RATE" in w]
    assert not drift_warnings, f"Unexpected drift warning: {report.warnings}"

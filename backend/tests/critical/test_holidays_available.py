"""
test_holidays_available.py
Assert that the holidays package is installed and that
_compute_holiday_flag raises ImportError when it is absent
(not silently falls back to a different feature definition).
"""
import importlib
import sys
import pytest
import pandas as pd


def test_holidays_package_importable():
    """holidays==0.46 must be installed — no silent fallback allowed."""
    hol = importlib.import_module("holidays")
    assert hasattr(hol, "country_holidays"), "holidays.country_holidays not found"


def test_holidays_us_calendar_has_entries():
    import holidays as hol
    us_2017 = hol.country_holidays("US", years=2017)
    assert len(us_2017) > 0, "US 2017 holiday calendar is empty"


def test_compute_holiday_flag_raises_without_package(monkeypatch):
    """If holidays is not installed, _compute_holiday_flag must raise, not warn."""
    import app.feature_engineering as fe

    original = sys.modules.get("holidays")
    monkeypatch.setitem(sys.modules, "holidays", None)  # simulate missing package
    try:
        df = pd.DataFrame({
            "order date (DateOrders)": ["1/15/2017 10:00"],
            "order_month": [1],
        })
        with pytest.raises((ImportError, TypeError)):
            fe._compute_holiday_flag(df, "order date (DateOrders)")
    finally:
        if original is not None:
            sys.modules["holidays"] = original
        elif "holidays" in sys.modules:
            del sys.modules["holidays"]


def test_holiday_flag_marks_christmas_period():
    """Dec 25 ± 3 days should be flagged as holiday period."""
    import app.feature_engineering as fe
    df = pd.DataFrame({
        "order date (DateOrders)": ["12/25/2017 12:00", "7/4/2017 12:00", "3/15/2017 12:00"],
        "Order Country": ["United States", "United States", "United States"],
        "order_month": [12, 7, 3],
    })
    result = fe._compute_holiday_flag(df, "order date (DateOrders)")
    assert result.iloc[0] == 1, "Christmas should be flagged"
    assert result.iloc[2] == 0, "Mid-March should not be flagged"

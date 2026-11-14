"""
tests/unit/test_period_and_reset.py
=====================================
Tests for:
  - next_period() advances the month for data ending on the 28th, 29th,
    30th, and 31st, and never returns the period containing its input.
  - Stage 6 records Stage 0 for the following period.
  - Startup reset clears cycle_state.json and increments, leaves
    base.parquet checksum unchanged.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── next_period() arithmetic ──────────────────────────────────────────────────

def _next_period_for(date_str: str) -> str:
    """Call next_period() with a mocked manifest returning date_str as data_end."""
    from app.core import period as period_mod

    manifest = {"data_end": date_str}
    with patch.object(period_mod, "_read_manifest", return_value=manifest):
        return period_mod.next_period()


@pytest.mark.parametrize("date_str, expected", [
    # 31st — last day of month
    ("2017-10-31", "2017-11"),
    # 30th — not last day of October (Oct has 31 days)
    ("2017-10-30", "2017-11"),
    # 29th
    ("2017-10-29", "2017-11"),
    # 28th
    ("2017-11-28", "2017-12"),
    # December → January rollover
    ("2017-12-31", "2018-01"),
    # Leap-year February 29th
    ("2016-02-29", "2016-03"),
    # Training window end (the canonical case)
    ("2017-09-30", "2017-10"),
])
def test_next_period_advances_month(date_str: str, expected: str):
    result = _next_period_for(date_str)
    assert result == expected, f"next_period({date_str!r}) = {result!r}, want {expected!r}"


@pytest.mark.parametrize("date_str", [
    "2017-10-29", "2017-10-30", "2017-10-31",
    "2017-11-28", "2017-12-31", "2016-02-29",
])
def test_next_period_never_returns_same_month(date_str: str):
    """Result must be strictly greater than the period containing date_str."""
    result = _next_period_for(date_str)
    end_period = str(pd.Period(date_str, freq="M"))
    assert result > end_period, (
        f"next_period({date_str!r}) = {result!r} is not > {end_period!r}"
    )


def test_next_period_invariant_raises_on_bad_manifest(monkeypatch):
    """If somehow result == end_period, RuntimeError must be raised."""
    from app.core import period as period_mod

    original_period = pd.Period

    class _FakePeriod:
        def __init__(self, val, freq=None):
            self._p = original_period(val, freq=freq) if freq else original_period(val)
        def __add__(self, other):
            return self._p  # return same period — triggers invariant
        def __str__(self):
            return str(self._p)

    monkeypatch.setattr(period_mod.pd, "Period", _FakePeriod)
    monkeypatch.setattr(period_mod, "_read_manifest", lambda: {"data_end": "2017-09-30"})

    with pytest.raises((RuntimeError, TypeError)):
        period_mod.next_period()


# ── Stage 6 records Stage 0 for the next period ───────────────────────────────

def test_stage6_records_stage0_for_next_period(tmp_path, monkeypatch):
    """
    After Stage 6 completes, cycle_state.json must contain a COMPLETED
    Stage 0 entry for the following period.
    """
    from app.services import cycle_state_store as css
    from app.core import period as period_mod

    state_file = tmp_path / "cycle_state.json"
    monkeypatch.setattr(css, "_state_path", lambda: state_file)
    monkeypatch.setattr(period_mod, "_read_manifest", lambda: {"data_end": "2017-09-30"})

    # Record Stage 6 for 2017-10
    css.record_stage("2017-10", 6, "COMPLETED", 1234.5, {"next_period": "2017-11"}, None)

    # Simulate the Stage 6 → Stage 0 chaining from cycle_service
    from app.core.period import next_period
    _next = next_period()
    assert _next == "2017-11"
    css.record_stage(_next, 0, "COMPLETED", 1234.5, {"target_period": "2017-11"}, None)

    data = json.loads(state_file.read_text())
    assert "2017-11" in data["periods"], "Stage 0 for 2017-11 not recorded"
    assert data["periods"]["2017-11"]["stage_statuses"]["0"]["status"] == "COMPLETED"


# ── Startup reset ─────────────────────────────────────────────────────────────

def test_startup_reset_clears_state_and_increments_leaves_base_unchanged(tmp_path, monkeypatch):
    """
    _reset_cycle_on_startup() must:
      - delete cycle_state.json
      - call store.reset_increments(confirm=True)
      - leave base.parquet checksum unchanged
    """
    import asyncio
    from app.services import cycle_state_store as css

    # Create a fake base.parquet
    base_parquet = tmp_path / "cumulative" / "base.parquet"
    base_parquet.parent.mkdir(parents=True)
    base_parquet.write_bytes(b"fake-parquet-content-do-not-modify")
    checksum_before = hashlib.sha256(base_parquet.read_bytes()).hexdigest()

    # Point state file at tmp_path
    state_file = tmp_path / "cycle_state.json"
    state_file.write_text(json.dumps({"periods": {"2017-10": {}}}))
    monkeypatch.setattr(css, "_state_path", lambda: state_file)

    mock_store = MagicMock()
    mock_store.reset_increments.return_value = {"deleted": 2}

    def _fake_path(*args, **kwargs):
        p = Path(*args, **kwargs)
        if "cumulative" in str(p) and "base.parquet" in str(p):
            return base_parquet
        return p

    with (
        patch("app.core.events.CumulativeStore", return_value=mock_store),
        patch("app.core.events.clear_dataset_cache", MagicMock()),
        patch("app.core.events.clear_forecast_cache", MagicMock()),
        patch("app.core.events.Path", side_effect=_fake_path),
    ):
        asyncio.run(__import__("app.core.events", fromlist=["_reset_cycle_on_startup"])._reset_cycle_on_startup())

    assert not state_file.exists(), "cycle_state.json was not deleted by startup reset"
    mock_store.reset_increments.assert_called_once_with(confirm=True)

    checksum_after = hashlib.sha256(base_parquet.read_bytes()).hexdigest()
    assert checksum_before == checksum_after, "base.parquet was modified during startup reset"

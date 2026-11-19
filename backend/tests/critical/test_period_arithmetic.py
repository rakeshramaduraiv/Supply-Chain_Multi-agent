"""
tests/critical/test_period_arithmetic.py
==========================================
Tests for Defect 1 (next_period arithmetic) and Defect 3 (path resolution).

Covers:
  - next_period advances the month for data ends on the 28th, 29th, 30th, 31st
  - next_period rolls December to January correctly
  - next_period never returns the period containing its input
  - current_data_end resolves correctly regardless of working directory
  - initialization raises when use_real_holdout_actuals=True and holdout_start_date=None
"""
from __future__ import annotations

import os
import pathlib
from unittest.mock import patch

import pandas as pd
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _next_for(date_str: str) -> str:
    """Call next_period() with current_data_end mocked to date_str."""
    from app.core import period as period_mod
    ts = pd.Timestamp(date_str)
    with patch.object(period_mod, "current_data_end", return_value=ts):
        return period_mod.next_period()


# ── Defect 1: period arithmetic ───────────────────────────────────────────────

class TestNextPeriodArithmetic:
    """next_period() must advance the calendar month regardless of day."""

    def test_end_on_28th(self):
        assert _next_for("2017-11-28") == "2017-12"

    def test_end_on_29th(self):
        assert _next_for("2017-10-29") == "2017-11"

    def test_end_on_30th(self):
        assert _next_for("2017-09-30") == "2017-10"

    def test_end_on_31st(self):
        assert _next_for("2017-10-31") == "2017-11"

    def test_december_to_january(self):
        assert _next_for("2017-12-15") == "2018-01"

    def test_december_31_to_january(self):
        assert _next_for("2017-12-31") == "2018-01"

    def test_february_leap_year(self):
        # 2016 is a leap year — Feb 29 exists
        assert _next_for("2016-02-29") == "2016-03"

    def test_february_non_leap(self):
        assert _next_for("2017-02-28") == "2017-03"

    def test_never_returns_same_month(self):
        """next_period() must never return the period containing its input."""
        test_dates = [
            "2017-09-01", "2017-09-15", "2017-09-30",
            "2017-10-01", "2017-10-15", "2017-10-31",
            "2017-11-01", "2017-11-28",
            "2017-12-01", "2017-12-31",
        ]
        from app.core import period as period_mod
        for date_str in test_dates:
            ts = pd.Timestamp(date_str)
            with patch.object(period_mod, "current_data_end", return_value=ts):
                result = period_mod.next_period()
            input_period = ts.strftime("%Y-%m")
            assert result != input_period, (
                f"next_period() returned {result!r} for input {date_str!r} "
                f"(input period={input_period!r}) — same month returned"
            )
            assert result > input_period, (
                f"next_period() returned {result!r} which is not strictly "
                f"greater than input period {input_period!r}"
            )

    def test_holdout_months_all_advance(self):
        """Verify all four holdout month-ends advance correctly."""
        cases = [
            ("2017-10-31", "2017-11"),
            ("2017-11-30", "2017-12"),
            ("2017-12-31", "2018-01"),
            ("2018-01-31", "2018-02"),
        ]
        for date_str, expected in cases:
            assert _next_for(date_str) == expected, (
                f"next_period() for {date_str!r}: expected {expected!r}"
            )


# ── Defect 3: path resolution ─────────────────────────────────────────────────

class TestPathResolution:
    """current_data_end must resolve correctly regardless of CWD."""

    def test_manifest_path_is_absolute(self):
        from app.core.period import _MANIFEST_PATH
        assert _MANIFEST_PATH.is_absolute(), (
            f"_MANIFEST_PATH is not absolute: {_MANIFEST_PATH}"
        )

    def test_base_parquet_path_is_absolute(self):
        from app.core.period import _BASE_PARQUET
        assert _BASE_PARQUET.is_absolute(), (
            f"_BASE_PARQUET is not absolute: {_BASE_PARQUET}"
        )

    def test_cumulative_store_base_dir_is_absolute(self):
        from app.store.cumulative import _BASE_DIR
        assert _BASE_DIR.is_absolute(), (
            f"CumulativeStore _BASE_DIR is not absolute: {_BASE_DIR}"
        )

    def test_current_data_end_stable_across_cwd(self, tmp_path, monkeypatch):
        """
        current_data_end() must return the same value regardless of CWD.
        We mock the manifest to return a known value and change CWD.
        """
        from app.core import period as period_mod

        known_end = "2017-09-30"
        manifest_data = {"data_end": known_end}

        with patch.object(period_mod, "_read_manifest", return_value=manifest_data):
            # Change CWD to tmp_path (completely unrelated directory)
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp_path)
                result = period_mod.current_data_end()
            finally:
                os.chdir(original_cwd)

        assert result == pd.Timestamp(known_end), (
            f"current_data_end() returned {result} when CWD={tmp_path}"
        )

    def test_fallback_logs_warning_when_manifest_missing(self, caplog):
        """When manifest is absent, a WARNING must be logged (Defect 3c)."""
        import logging
        from app.core import period as period_mod

        with patch.object(period_mod, "_read_manifest", return_value={}), \
             patch.object(period_mod, "_BASE_PARQUET", pathlib.Path("/nonexistent/base.parquet")), \
             caplog.at_level(logging.WARNING, logger="app.core.period"):
            result = period_mod.current_data_end()

        assert result == period_mod._FALLBACK_END
        assert any("fallback" in r.message.lower() or "falling back" in r.message.lower()
                   for r in caplog.records), (
            "Expected a WARNING log mentioning fallback when manifest is missing"
        )


# ── Defect 4: holdout guard ───────────────────────────────────────────────────

class TestHoldoutGuardDefaults:
    """use_real_holdout_actuals=True with holdout_start_date=None must raise."""

    def test_default_holdout_start_date_is_set(self):
        """Default holdout_start_date must not be None (Defect 4a)."""
        from app.core.config import Settings
        s = Settings()
        assert s.holdout_start_date is not None, (
            "holdout_start_date default is None — safe default must be '2017-10-01'"
        )

    def test_default_use_real_holdout_actuals_is_true(self):
        """Default use_real_holdout_actuals must be True (Defect 4a)."""
        from app.core.config import Settings
        s = Settings()
        assert s.use_real_holdout_actuals is True, (
            "use_real_holdout_actuals default is False — safe default must be True"
        )

    def test_startup_raises_when_guard_incoherent(self):
        """
        on_startup must raise RuntimeError when use_real_holdout_actuals=True
        and holdout_start_date=None (Defect 4b).
        """
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from app.core import events

        bad_settings = MagicMock()
        bad_settings.use_real_holdout_actuals = True
        bad_settings.holdout_start_date = None
        bad_settings.upload_dir = "/tmp"
        bad_settings.model_dir = "/tmp"
        bad_settings.log_dir = "/tmp"

        with patch.object(events, "settings", bad_settings), \
             patch("app.initialization.startup.check_and_initialize", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="holdout_start_date is None"):
                asyncio.run(events.on_startup())


# ── Stage 6 → Stage 0 recording ──────────────────────────────────────────────

class TestStage6RecordsStage0:
    """Stage 6 of cycle N must always record Stage 0 for cycle N+1."""

    def test_stage6_records_next_period_stage0(self, tmp_path):
        """
        After a successful Stage 6, _record_stage must be called with
        the next period and stage=0.
        """
        from unittest.mock import MagicMock, patch, AsyncMock
        import asyncio
        from app.services import cycle_service

        # Minimal DataFrame that passes Stage 1
        df = pd.DataFrame({
            "Late_delivery_risk":  [0, 1],
            "Order Item Quantity": [2, 3],
            "Department Name":     ["A", "B"],
            "Product Card Id":     ["P1", "P2"],
            "Shipping Mode":       ["Standard", "Express"],
            "Order Region":        ["East", "West"],
            "order date (DateOrders)": ["2017-10-01", "2017-10-15"],
        })

        recorded: list[tuple] = []

        def fake_record_stage(period, stage, status, *args, **kwargs):
            recorded.append((period, stage, status))

        with patch.object(cycle_service, "_record_stage", side_effect=fake_record_stage), \
             patch.object(cycle_service, "_stage1_ingest_validate",
                   return_value=(MagicMock(stage=1, name="Ingest", status="COMPLETED",
                                           duration_ms=1.0, detail={}, error=None), df, [])), \
             patch("app.core.period.current_data_end",
                   return_value=pd.Timestamp("2017-10-31")), \
             patch("app.ingestion.schema_adapter.adapt",
                   return_value=(df, MagicMock(ok=True, missing=[], resolved=[]))), \
             patch("app.ingestion.continuity.validate_continuity",
                   return_value=MagicMock(warnings=[])), \
             patch.object(cycle_service, "_stage2_match_forecast",
                   return_value=(MagicMock(stage=2, name="Match", status="SKIPPED",
                                           duration_ms=1.0, detail={"reason": "no forecast"},
                                           error=None), pd.DataFrame(), df)), \
             patch.object(cycle_service, "_stage3_compute_metrics",
                   return_value=(MagicMock(stage=3, name="Metrics", status="SKIPPED",
                                           duration_ms=1.0, detail={"reason": "no forecast"},
                                           error=None), None)), \
             patch.object(cycle_service, "_stage4_tpke",
                   return_value=MagicMock(stage=4, name="TPKE", status="SKIPPED",
                                          duration_ms=1.0, detail={}, error=None)), \
             patch.object(cycle_service, "_stage5_store_and_retrain",
                   return_value=(MagicMock(stage=5, name="Store", status="COMPLETED",
                                           duration_ms=1.0, detail={}, error=None), 1000)), \
             patch.object(cycle_service, "_stage6_forecast_next",
                   return_value=MagicMock(stage=6, name="Forecast", status="COMPLETED",
                                          duration_ms=1.0, detail={"target_period": "2017-11"},
                                          error=None)):

            result = asyncio.run(cycle_service.run_upload_cycle(
                df_actual=df, period="2017-10", filename="test.csv",
            ))

        # Stage 0 for "2017-11" must NOT have been recorded (Part A3 / H6)
        stage0_records = [(p, s, st) for p, s, st in recorded if s == 0]
        assert not any(p == "2017-11" and st == "COMPLETED"
                       for p, s, st in stage0_records), (
            f"Stage 0 for '2017-11' was unexpectedly recorded. All records: {recorded}"
        )

"""
tests/critical/test_lfs_and_preflight.py
==========================================
Tests for:
  - assert_real_file raises on LFS pointer bytes
  - _available_periods raises when manifest lacks 'split' column
  - preflight reports ready=false when registry.json is absent
  - Stage 0 returns reason NOT_INITIALIZED when models are missing
  - with all prerequisites present, available-periods returns 4 periods
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ── 1. assert_real_file raises on LFS magic bytes ────────────────────────────

def test_assert_real_file_raises_on_lfs_pointer(tmp_path):
    from app.core.data_files import assert_real_file, LFS_MAGIC

    lfs_file = tmp_path / "pointer.csv"
    lfs_file.write_bytes(LFS_MAGIC + b"\noid sha256:abc123\nsize 1234567\n")

    with pytest.raises(RuntimeError, match="LFS pointer"):
        assert_real_file(lfs_file)


def test_assert_real_file_passes_on_real_csv(tmp_path):
    from app.core.data_files import assert_real_file

    real_file = tmp_path / "real.csv"
    real_file.write_text("col1,col2\n1,2\n3,4\n")

    assert_real_file(real_file)  # must not raise


def test_assert_real_file_raises_on_missing(tmp_path):
    from app.core.data_files import assert_real_file

    with pytest.raises(FileNotFoundError):
        assert_real_file(tmp_path / "nonexistent.csv")


# ── 2. _available_periods raises when manifest lacks 'split' column ──────────

def test_available_periods_raises_on_missing_split_column(tmp_path):
    """A manifest without 'split' must raise RuntimeError, not return []."""
    bad_manifest = tmp_path / "holdout_manifest.csv"
    bad_manifest.write_text("wrong_col,other_col\nval1,val2\n")

    with patch("app.services.cycle_state_store.resolve_actuals_dir", return_value=tmp_path):
        from app.services.cycle_state_store import _available_periods
        with pytest.raises(RuntimeError, match="missing required columns"):
            _available_periods()


def test_available_periods_skips_lfs_csv_files(tmp_path):
    """Actuals CSVs that are LFS pointers are skipped with a warning."""
    from app.core.data_files import LFS_MAGIC

    # Valid manifest
    manifest = tmp_path / "holdout_manifest.csv"
    manifest.write_text(
        "split,rows,date_min,date_max\n"
        "train,1000,2015-01-01,2017-09-30\n"
        "2017-10,200,2017-10-01,2017-10-31\n"
    )
    # LFS pointer actuals file
    lfs_csv = tmp_path / "2017_10_actual.csv"
    lfs_csv.write_bytes(LFS_MAGIC + b"\noid sha256:abc\nsize 1234567\n")

    with patch("app.services.cycle_state_store.resolve_actuals_dir", return_value=tmp_path):
        from app.services.cycle_state_store import _available_periods
        result = _available_periods()
    # LFS file skipped → empty list
    assert result == []


def test_available_periods_returns_four_real_periods(tmp_path):
    """With real CSVs and a valid manifest, returns all 4 holdout periods."""
    manifest = tmp_path / "holdout_manifest.csv"
    manifest.write_text(
        "split,rows,date_min,date_max\n"
        "train,171962,2015-01-01,2017-09-30\n"
        "2017-10,2255,2017-10-01,2017-10-31\n"
        "2017-11,2055,2017-11-01,2017-11-30\n"
        "2017-12,2124,2017-12-01,2017-12-31\n"
        "2018-01,2123,2018-01-01,2018-01-31\n"
    )
    for period in ["2017-10", "2017-11", "2017-12", "2018-01"]:
        fname = period.replace("-", "_") + "_actual.csv"
        (tmp_path / fname).write_text("col1,col2\n1,2\n")

    with patch("app.services.cycle_state_store.resolve_actuals_dir", return_value=tmp_path):
        from app.services.cycle_state_store import _available_periods
        result = _available_periods()

    assert len(result) == 4
    assert [r["period"] for r in result] == ["2017-10", "2017-11", "2017-12", "2018-01"]


# ── 3. preflight reports ready=false when registry.json is absent ────────────

@pytest.mark.anyio
async def test_preflight_fails_when_registry_missing(tmp_path):
    """preflight must return ready=false with model_registry in blocking_issues."""
    from app.api.v1.endpoints.cycle_routes import cycle_preflight

    # Patch settings to point at tmp_path where registry.json does not exist
    mock_settings = MagicMock()
    mock_settings.raw_data_dir = str(tmp_path)
    mock_settings.upload_dir = str(tmp_path)
    mock_settings.model_dir = str(tmp_path)  # no registry.json here

    with patch("app.api.v1.endpoints.cycle_routes.Path") as _p, \
         patch("app.core.data_files.resolve_actuals_dir", return_value=tmp_path):
        # Use real Path but override settings
        with patch("app.core.config.get_settings", return_value=mock_settings):
            result = await cycle_preflight()

    assert result["ready"] is False
    names = [c["name"] for c in result["checks"] if not c["passed"]]
    assert "model_registry" in names


# ── 4. Stage 0 returns NOT_INITIALIZED when models are missing ───────────────

@pytest.mark.anyio
async def test_stage0_returns_not_initialized_reason():
    """issue_forecast must raise 422 with reason=NOT_INITIALIZED when not ready."""
    from fastapi import HTTPException
    from app.api.v1.endpoints.cycle_routes import issue_forecast

    mock_forecast = {"ready": False, "message": "No model found in registry"}

    with patch("app.api.v1.endpoints.dataset_summary._compute_auto_forecast",
               return_value=mock_forecast), \
         patch("app.services.cycle_state_store.get_cycle_state_response",
               return_value={"next_expected_period": "2017-10"}), \
         patch("app.services.cycle_state_store.get_period_state", return_value=None), \
         patch("app.services.cycle_state_store.record_stage"):
        with pytest.raises(HTTPException) as exc_info:
            await issue_forecast("2017-10")

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert detail["reason"] == "NOT_INITIALIZED"

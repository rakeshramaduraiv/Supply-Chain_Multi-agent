"""
Tests for SnapshotWriter — backend/tests/test_stage_snapshots.py
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from app.initialization.snapshots import SnapshotWriter, _PII_COLUMNS, _BANNED_FROM_MODELS


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_df(n: int, extra_cols: list[str] | None = None) -> pd.DataFrame:
    data = {
        "order_id": list(range(n)),
        "qty": [float(i % 10) for i in range(n)],
        "late_risk": [i % 2 for i in range(n)],
    }
    for col in (extra_cols or []):
        data[col] = [f"val_{i}" for i in range(n)]
    return pd.DataFrame(data)


# ── test 1 ────────────────────────────────────────────────────────────────────

def test_snapshot_creates_three_files(tmp_path):
    snap = SnapshotWriter(tmp_path, sample_rows=100)
    snap.write(1, "raw", _make_df(200))

    assert (tmp_path / "1_raw.csv").exists(), "sample CSV missing"
    assert (tmp_path / "1_raw_full.parquet").exists(), "full parquet missing"
    assert (tmp_path / "1_raw_profile.csv").exists(), "profile CSV missing"


# ── test 2 ────────────────────────────────────────────────────────────────────

def test_sample_takes_head_and_tail(tmp_path):
    n, sample_size, half = 5_000, 2_000, 1_000
    df = _make_df(n)

    snap = SnapshotWriter(tmp_path, sample_rows=sample_size)
    snap.write(1, "raw", df)

    sample = pd.read_csv(tmp_path / "1_raw.csv")
    assert len(sample) == sample_size

    # First half = rows 0..999
    assert list(sample["order_id"].iloc[:half]) == list(range(half))
    # Last half = rows 4000..4999
    assert list(sample["order_id"].iloc[half:]) == list(range(n - half, n))


# ── test 3 ────────────────────────────────────────────────────────────────────

def test_pii_columns_redacted(tmp_path):
    pii_col = "Customer Password"
    df = _make_df(100, extra_cols=[pii_col])

    snap = SnapshotWriter(tmp_path, sample_rows=50)
    snap.write(1, "raw", df)

    assert pii_col not in pd.read_csv(tmp_path / "1_raw.csv").columns
    assert pii_col not in pd.read_parquet(tmp_path / "1_raw_full.parquet").columns
    assert pii_col not in pd.read_csv(tmp_path / "1_raw_profile.csv")["column"].values


# ── test 4 ────────────────────────────────────────────────────────────────────

def test_manifest_tracks_new_columns(tmp_path):
    snap = SnapshotWriter(tmp_path, sample_rows=50)
    snap.write(1, "raw", _make_df(100))
    snap.write(2, "cleaned", _make_df(100, extra_cols=["new_feature_x"]))
    snap.finalize()

    manifest = json.loads((tmp_path / "00_manifest.json").read_text(encoding="utf-8"))
    stage2 = next(r for r in manifest if r["stage_no"] == 2)
    assert "new_feature_x" in stage2["new_columns"]


# ── test 5 ────────────────────────────────────────────────────────────────────

def test_snapshot_failure_does_not_raise(tmp_path, caplog):
    snap = SnapshotWriter(tmp_path, sample_rows=50)
    df = _make_df(100)

    with patch("pandas.DataFrame.to_parquet", side_effect=OSError("disk full")):
        with caplog.at_level(logging.WARNING):
            result = snap.write(1, "raw", df)

    assert result == {}
    assert any(
        "disk full" in r.message or "failed" in r.message.lower()
        for r in caplog.records
    )


# ── test 6 ────────────────────────────────────────────────────────────────────

def test_disabled_flag_is_noop(tmp_path):
    stage_dir = tmp_path / "stages"
    snap = SnapshotWriter(stage_dir, sample_rows=50, disabled=True)
    snap.write(1, "raw", _make_df(100))
    snap.write(2, "cleaned", _make_df(100))
    snap.finalize()

    files = list(stage_dir.glob("*")) if stage_dir.exists() else []
    assert files == [], f"Expected no snapshot files created when disabled, found: {files}"


# ── test 7 ────────────────────────────────────────────────────────────────────

def test_graph_delta_written(tmp_path):
    df_tier1 = pd.DataFrame({
        "graph_supplier_reliability": [0.8, 0.9, 0.7],
        "graph_inventory_stress": [0.1, 0.2, 0.3],
        "graph_avg_shipping_delay": [1.0, 2.0, 1.5],
    })
    df_enriched = pd.DataFrame({
        "graph_supplier_reliability": [0.85, 0.95, 0.65],
        "graph_inventory_stress": [0.1, 0.2, 0.3],
        "graph_avg_shipping_delay": [1.2, 2.1, 1.4],
    })

    snap = SnapshotWriter(tmp_path, sample_rows=50)
    snap.write(4, "graph_enriched", df_enriched, tier1_graph=df_tier1)

    delta_file = tmp_path / "4_graph_delta.csv"
    assert delta_file.exists()

    delta = pd.read_csv(delta_file)
    assert "graph_supplier_reliability" in delta["column"].values
    reliability_row = delta[delta["column"] == "graph_supplier_reliability"].iloc[0]
    assert reliability_row["mean_abs_change"] > 0
    assert reliability_row["pct_rows_changed"] > 0


# ── test 8 ────────────────────────────────────────────────────────────────────

def test_banned_from_models_in_stage5_profile(tmp_path):
    df = _make_df(10, extra_cols=["is_delayed", "delivery_gap"])

    snap = SnapshotWriter(tmp_path, sample_rows=50)
    snap.write(5, "training_input", df)

    prof = pd.read_csv(tmp_path / "5_training_input_profile.csv")
    assert "is_banned_from_models" in prof.columns

    banned_map = dict(zip(prof["column"], prof["is_banned_from_models"]))
    assert banned_map["is_delayed"] == True
    assert banned_map["delivery_gap"] == True
    assert banned_map["order_id"] == False


# ── test 9 ────────────────────────────────────────────────────────────────────

def test_column_lineage_shows_new_features(tmp_path):
    snap = SnapshotWriter(tmp_path, sample_rows=50)
    snap.write(1, "raw", _make_df(100))
    snap.write(3, "tier1_features", _make_df(100, extra_cols=["qty_roll_7", "qty_roll_30"]))
    snap.finalize()

    lineage = pd.read_csv(tmp_path / "00_column_lineage.csv")
    row = lineage[lineage["column"] == "qty_roll_7"].iloc[0]

    assert row["s01_raw"] == False, "qty_roll_7 should NOT exist at stage 1"
    assert row["s03_tier1_features"] == True, "qty_roll_7 SHOULD exist at stage 3"

"""
Tests for StageExporter and quality report.
backend/tests/test_stage_exporter.py
"""
import logging
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.initialization.stage_exporter import StageExporter
from app.data_engineering.quality_report import build_quality_report


# ── helpers ───────────────────────────────────────────────────────────────────

def _df(n: int, extra: list[str] | None = None) -> pd.DataFrame:
    data = {
        "order_id": range(n),
        "qty":      [float(i % 10) for i in range(n)],
        "risk":     [i % 2 for i in range(n)],
    }
    for c in (extra or []):
        data[c] = [f"v{i}" for i in range(n)]
    return pd.DataFrame(data)


def _exporter(tmp_path: Path, sample_rows: int = 2000, **kw) -> StageExporter:
    return StageExporter(out_dir=str(tmp_path), sample_rows=sample_rows, **kw)


# ── test 1 ────────────────────────────────────────────────────────────────────

def test_export_creates_three_files(tmp_path):
    exp = _exporter(tmp_path)
    exp.export(1, "raw", _df(200))
    assert (tmp_path / "1_raw_sample.csv").exists()
    assert (tmp_path / "1_raw_full.parquet").exists()
    assert (tmp_path / "1_raw_profile.csv").exists()


# ── test 2 ────────────────────────────────────────────────────────────────────

def test_sample_head_and_tail(tmp_path):
    n, half = 5000, 1000
    exp = _exporter(tmp_path, sample_rows=2000)
    exp.export(1, "raw", _df(n))
    sample = pd.read_csv(tmp_path / "1_raw_sample.csv")
    assert len(sample) == 2000
    assert list(sample["order_id"].iloc[:half]) == list(range(half))
    assert list(sample["order_id"].iloc[half:]) == list(range(n - half, n))


# ── test 3 ────────────────────────────────────────────────────────────────────

def test_pii_redacted(tmp_path):
    pii = "Customer Password"
    exp = _exporter(tmp_path)
    exp.export(1, "raw", _df(100, extra=[pii]))
    for fname in ["1_raw_sample.csv", "1_raw_profile.csv"]:
        assert pii not in pd.read_csv(tmp_path / fname).columns
    assert pii not in pd.read_parquet(tmp_path / "1_raw_full.parquet").columns


# ── test 4 ────────────────────────────────────────────────────────────────────

def test_manifest_columns_added(tmp_path):
    exp = _exporter(tmp_path)
    exp.export(1, "raw",     _df(100))
    exp.export(2, "cleaned", _df(100, extra=["new_feat"]))
    exp.finalize()
    import json
    manifest = json.loads((tmp_path / "00_pipeline_summary.json").read_text())
    s2 = next(r for r in manifest if r["step"] == 2)
    assert "new_feat" in s2["columns_added"]


# ── test 5 ────────────────────────────────────────────────────────────────────

def test_exception_does_not_propagate(tmp_path, caplog):
    exp = _exporter(tmp_path)
    with patch("pandas.DataFrame.to_parquet", side_effect=OSError("disk full")):
        with caplog.at_level(logging.WARNING):
            result = exp.export(1, "raw", _df(100))
    assert result == {}
    assert any("disk full" in r.message or "failed" in r.message.lower()
               for r in caplog.records)


# ── test 6 ────────────────────────────────────────────────────────────────────

def test_disabled_creates_no_files(tmp_path):
    exp = _exporter(tmp_path, disabled=True)
    exp.export(1, "raw",     _df(100))
    exp.export(2, "cleaned", _df(100))
    exp.finalize()
    assert list(tmp_path.iterdir()) == []


# ── test 7 ────────────────────────────────────────────────────────────────────

def test_quality_report_detects_delivery_status_proxy():
    n = 1000
    df = pd.DataFrame({
        "Delivery Status": (["Late delivery"] * 500 + ["Shipping on time"] * 500),
        "Late_delivery_risk": ([1] * 500 + [0] * 500),
        "Order Item Quantity": np.random.randint(1, 10, n),
    })
    report = build_quality_report(df, df)
    q1 = report[report["issue_id"] == "Q1"]
    assert len(q1) == 1
    assert q1.iloc[0]["severity"] == "CRITICAL"


# ── test 8 ────────────────────────────────────────────────────────────────────

def test_quality_report_detects_duplicate_columns():
    n = 500
    col_a = np.random.rand(n)
    df = pd.DataFrame({
        "Benefit per order":       col_a,
        "Order Profit Per Order":  col_a,   # exact duplicate
        "Late_delivery_risk":      np.random.randint(0, 2, n),
    })
    report = build_quality_report(df, df)
    q2 = report[report["issue_id"] == "Q2"]
    assert len(q2) == 1
    assert "Benefit per order" in q2.iloc[0]["affected_columns"] or \
           "Order Profit Per Order" in q2.iloc[0]["affected_columns"]


# ── test 9 ────────────────────────────────────────────────────────────────────

def test_delivery_status_not_in_any_feature_list():
    from app.ml.utils import DEMAND_FEATURES, SUPPLIER_FEATURES, LOGISTICS_FEATURES
    for name, feats in [("demand", DEMAND_FEATURES),
                        ("supplier", SUPPLIER_FEATURES),
                        ("logistics", LOGISTICS_FEATURES)]:
        assert "Delivery Status" not in feats, \
            f"'Delivery Status' found in {name.upper()}_FEATURES — must be banned"

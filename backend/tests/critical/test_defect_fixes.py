"""
Tests for Defect 1 (collaborative pipeline per-entity predictions) and
Defect 2/3 (CumulativeStore load_full, append, holdout boundary, coverage endpoint).
"""

import json
import logging
import pathlib
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_store(tmp_path):
    """Return a CumulativeStore backed by a temp directory."""
    from app.store.cumulative import CumulativeStore
    return CumulativeStore(base_dir=tmp_path)


def _make_base_df(n=200, max_date="2017-09-30"):
    """Synthetic base DataFrame with required columns."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2015-01-01", max_date, periods=n)
    return pd.DataFrame({
        "order date (DateOrders)": dates,
        "Order Region": rng.choice(["Western Europe", "Central America", "South Asia", "East Asia"], n),
        "Category Name": rng.choice(["Fishing", "Cleats", "Camping"], n),
        "Order Item Quantity": rng.integers(1, 10, n).astype(float),
        "Late_delivery_risk": rng.integers(0, 2, n).astype(float),
        "feature_a": rng.random(n),
        "feature_b": rng.random(n),
    })


def _make_increment_df(n=50, start_date="2017-10-01", end_date="2017-10-31"):
    """Synthetic increment with same columns as base."""
    rng = np.random.default_rng(99)
    dates = pd.date_range(start_date, end_date, periods=n)
    return pd.DataFrame({
        "order date (DateOrders)": dates,
        "Order Region": rng.choice(["Western Europe", "Central America", "South Asia", "East Asia"], n),
        "Category Name": rng.choice(["Fishing", "Cleats", "Camping"], n),
        "Order Item Quantity": rng.integers(1, 10, n).astype(float),
        "Late_delivery_risk": rng.integers(0, 2, n).astype(float),
        "feature_a": rng.random(n),
        "feature_b": rng.random(n),
    })


# ─────────────────────────────────────────────────────────────────────────────
# DEFECT 1 — Collaborative pipeline per-entity predictions
# ─────────────────────────────────────────────────────────────────────────────

class TestCollaborativePipelinePerEntity:
    """Coordinator returns distinct predictions across regions for varying features."""

    def _make_coordinator_with_mock_agents(self, demand_preds, supplier_probs, logistics_probs):
        """Build an AgentCoordinator whose agents return controlled predictions."""
        from app.ml.prediction.collaborative_pipeline import AgentCoordinator
        from app.ml.prediction import PredictionResult

        def _make_result(preds, probs=None, intel_type="demand"):
            return PredictionResult(
                intelligence_type=intel_type,
                model_version="test-v1",
                predictions=list(preds),
                probabilities=list(probs) if probs is not None else None,
                confidence_scores=[0.8] * len(preds),
                risk_levels=["medium"] * len(preds),
                mean_confidence=0.8,
                n_predictions=len(preds),
                prediction_time_ms=1.0,
            )

        coord = AgentCoordinator.__new__(AgentCoordinator)
        coord.pipeline = MagicMock()
        coord.event_bus = MagicMock()
        coord.event_bus.event_log = []
        coord.latest_summary = None
        coord._register_subscribers = lambda: None

        coord.pipeline.demand_agent.predict.return_value = _make_result(demand_preds, intel_type="demand")
        coord.pipeline.supplier_agent.predict.return_value = _make_result(
            [int(p >= 0.5) for p in supplier_probs], supplier_probs, intel_type="supplier"
        )
        coord.pipeline.logistics_agent.predict.return_value = _make_result(
            [int(p >= 0.5) for p in logistics_probs], logistics_probs, intel_type="logistics"
        )
        return coord

    def test_distinct_region_predictions(self):
        """Coordinator entity_predictions must contain distinct values across regions."""
        from app.ml.prediction.collaborative_pipeline import AgentCoordinator

        # Build a frame with 4 regions, each with 10 rows, varying features
        rng = np.random.default_rng(7)
        regions = ["Western Europe", "Central America", "South Asia", "East Asia"]
        rows = []
        for i, region in enumerate(regions):
            for _ in range(10):
                rows.append({
                    "Order Region": region,
                    "Category Name": "Fishing",
                    # Each region gets a different demand level
                    "demand_val": float(i * 2 + rng.random()),
                })
        df = pd.DataFrame(rows)

        # Demand predictions vary by region (simulate real model output)
        demand_preds = [row["demand_val"] for _, row in df.iterrows()]
        supplier_probs = [0.3 + 0.1 * i for i in range(len(df))]
        logistics_probs = [0.4 + 0.05 * i for i in range(len(df))]

        coord = self._make_coordinator_with_mock_agents(demand_preds, supplier_probs, logistics_probs)

        with patch("app.ml.agent_memory.get_agent_memory", return_value=MagicMock()), \
             patch("app.engine.decision_engine.DecisionEngine") as mock_de:
            mock_de.return_value.compute_decision.return_value = MagicMock(to_dict=lambda: {})
            result = coord.execute_coordinated_pipeline(df)

        d_payload = result.agent_payloads["Demand Planning Agent"]
        entity_preds = d_payload["entity_predictions"]
        region_preds = {e["entity_key"]: e["forecast_quantity"]
                        for e in entity_preds if e["entity_type"] == "Order Region"}

        assert len(region_preds) == 4, f"Expected 4 regions, got {len(region_preds)}"
        values = list(region_preds.values())
        assert len(set(values)) > 1, f"All region predictions are identical: {values}"

    def test_constant_prediction_logs_error(self, caplog):
        """A constant prediction vector across >1 rows must log an error."""
        from app.ml.prediction.collaborative_pipeline import AgentCoordinator
        from app.ml.prediction import PredictionResult

        df = pd.DataFrame({
            "Order Region": ["A", "B", "C"],
            "Category Name": ["X", "X", "X"],
        })
        constant_preds = [2.1, 2.1, 2.1]

        def _make_result(preds, probs=None, intel_type="demand"):
            return PredictionResult(
                intelligence_type=intel_type,
                model_version="test",
                predictions=list(preds),
                probabilities=list(probs) if probs is not None else None,
                confidence_scores=[0.8] * len(preds),
                risk_levels=["medium"] * len(preds),
                mean_confidence=0.8,
                n_predictions=len(preds),
                prediction_time_ms=1.0,
            )

        coord = AgentCoordinator.__new__(AgentCoordinator)
        coord.pipeline = MagicMock()
        coord.event_bus = MagicMock()
        coord.event_bus.event_log = []
        coord.latest_summary = None
        coord._register_subscribers = lambda: None
        coord.pipeline.demand_agent.predict.return_value = _make_result(constant_preds)
        coord.pipeline.supplier_agent.predict.return_value = _make_result([0.5, 0.5, 0.5], [0.5, 0.5, 0.5], "supplier")
        coord.pipeline.logistics_agent.predict.return_value = _make_result([0.4, 0.4, 0.4], [0.4, 0.4, 0.4], "logistics")

        with caplog.at_level(logging.ERROR, logger="app.ml.prediction.collaborative_pipeline"), \
             patch("app.ml.agent_memory.get_agent_memory", return_value=MagicMock()), \
             patch("app.engine.decision_engine.DecisionEngine") as mock_de:
            mock_de.return_value.compute_decision.return_value = MagicMock(to_dict=lambda: {})
            coord.execute_coordinated_pipeline(df)

        assert any("constant prediction" in r.message.lower() for r in caplog.records), \
            "Expected error log for constant prediction"

    def test_demand_unit_is_units_supplier_logistics_probability(self):
        """Demand payload unit='units'; supplier and logistics unit='probability'."""
        from app.ml.prediction.collaborative_pipeline import AgentCoordinator
        from app.ml.prediction import PredictionResult

        df = pd.DataFrame({"Order Region": ["A", "B"], "Category Name": ["X", "Y"]})

        def _make_result(preds, probs=None, intel_type="demand"):
            return PredictionResult(
                intelligence_type=intel_type,
                model_version="test",
                predictions=list(preds),
                probabilities=list(probs) if probs is not None else None,
                confidence_scores=[0.8] * len(preds),
                risk_levels=["medium"] * len(preds),
                mean_confidence=0.8,
                n_predictions=len(preds),
                prediction_time_ms=1.0,
            )

        coord = AgentCoordinator.__new__(AgentCoordinator)
        coord.pipeline = MagicMock()
        coord.event_bus = MagicMock()
        coord.event_bus.event_log = []
        coord.latest_summary = None
        coord._register_subscribers = lambda: None
        coord.pipeline.demand_agent.predict.return_value = _make_result([2.1, 3.0])
        coord.pipeline.supplier_agent.predict.return_value = _make_result([1, 0], [0.6, 0.4], "supplier")
        coord.pipeline.logistics_agent.predict.return_value = _make_result([1, 0], [0.55, 0.45], "logistics")

        with patch("app.ml.agent_memory.get_agent_memory", return_value=MagicMock()), \
             patch("app.engine.decision_engine.DecisionEngine") as mock_de:
            mock_de.return_value.compute_decision.return_value = MagicMock(to_dict=lambda: {})
            result = coord.execute_coordinated_pipeline(df)

        assert result.agent_payloads["Demand Planning Agent"]["prediction_unit"] == "units"
        assert result.agent_payloads["Supplier Intelligence Agent"]["prediction_unit"] == "probability"
        assert result.agent_payloads["Logistics & Transportation Agent"]["prediction_unit"] == "probability"


# ─────────────────────────────────────────────────────────────────────────────
# DEFECT 2 — CumulativeStore load_full
# ─────────────────────────────────────────────────────────────────────────────

class TestCumulativeStoreLoadFull:

    def test_load_full_returns_base_plus_increment(self, tmp_store):
        """load_full() returns base rows + increment rows in period order."""
        base_df = _make_base_df(100)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        inc_df = _make_increment_df(30)
        tmp_store.append(inc_df, "2017-10")

        full = tmp_store.load_full()
        assert len(full) == 130, f"Expected 130 rows, got {len(full)}"

    def test_load_full_reflects_new_increment_immediately(self, tmp_store):
        """load_full() reflects a new increment immediately after append."""
        base_df = _make_base_df(50)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        full_before = tmp_store.load_full()
        assert len(full_before) == 50

        inc_df = _make_increment_df(20)
        tmp_store.append(inc_df, "2017-10")

        full_after = tmp_store.load_full()
        assert len(full_after) == 70, f"Expected 70 rows after append, got {len(full_after)}"

    def test_append_missing_columns_raises(self, tmp_store):
        """Appending an increment whose columns differ from base raises ValueError."""
        base_df = _make_base_df(50)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        # Increment missing 'feature_b'
        inc_df = _make_increment_df(10).drop(columns=["feature_b"])
        with pytest.raises(ValueError, match="missing columns"):
            tmp_store.append(inc_df, "2017-10")

    def test_load_full_checksum_mismatch_raises(self, tmp_store):
        """load_full() raises ValueError if a listed increment has wrong checksum."""
        base_df = _make_base_df(50)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        inc_df = _make_increment_df(20)
        tmp_store.append(inc_df, "2017-10")

        # Corrupt the checksum in manifest
        manifest = tmp_store._read_manifest()
        manifest["checksums"]["2017-10"] = "deadbeef"
        tmp_store._write_manifest(manifest)
        tmp_store._invalidate_cache()

        with pytest.raises(ValueError, match="checksum mismatch"):
            tmp_store.load_full()

    def test_load_full_missing_increment_file_raises(self, tmp_store):
        """load_full() raises FileNotFoundError if a listed increment file is missing."""
        base_df = _make_base_df(50)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        inc_df = _make_increment_df(20)
        tmp_store.append(inc_df, "2017-10")

        # Delete the increment file but keep manifest entry
        (tmp_store._increments_dir / "2017-10.parquet").unlink()
        tmp_store._invalidate_cache()

        with pytest.raises(FileNotFoundError, match="missing"):
            tmp_store.load_full()


# ─────────────────────────────────────────────────────────────────────────────
# DEFECT 3 — Holdout boundary
# ─────────────────────────────────────────────────────────────────────────────

class TestHoldoutBoundary:

    def test_base_parquet_no_holdout_rows(self, tmp_store):
        """base.parquet must contain no row on or after holdout_start_date."""
        base_df = _make_base_df(100, max_date="2017-09-30")
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        # Should not raise
        tmp_store.assert_base_no_holdout("2017-10-01")

    def test_base_parquet_with_holdout_rows_raises(self, tmp_store):
        """assert_base_no_holdout raises if base contains holdout data."""
        base_df = _make_base_df(100, max_date="2017-11-30")  # past holdout
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        with pytest.raises(ValueError, match="holdout"):
            tmp_store.assert_base_no_holdout("2017-10-01")

    def test_append_never_modifies_base(self, tmp_store):
        """Appending an increment must never write into base.parquet."""
        base_df = _make_base_df(50)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        base_mtime_before = tmp_store._base_parquet.stat().st_mtime

        inc_df = _make_increment_df(20)
        tmp_store.append(inc_df, "2017-10")

        base_mtime_after = tmp_store._base_parquet.stat().st_mtime
        assert base_mtime_before == base_mtime_after, "base.parquet was modified by append"


# ─────────────────────────────────────────────────────────────────────────────
# Coverage endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestCoverageEndpoint:

    def test_coverage_reports_correct_combined_total(self, tmp_store):
        """coverage() reports the correct combined total after an append."""
        base_df = _make_base_df(100)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        inc_df = _make_increment_df(40)
        tmp_store.append(inc_df, "2017-10")

        cov = tmp_store.coverage()
        assert cov["base_row_count"] == 100
        assert cov["increment_count"] == 1
        assert cov["combined_total"] == 140
        assert cov["increments"][0]["period"] == "2017-10"
        assert cov["increments"][0]["rows"] == 40

    def test_coverage_endpoint_via_fastapi(self, tmp_store):
        """GET /dataset/coverage returns the correct combined total."""
        from fastapi.testclient import TestClient
        from app.api.v1.endpoints import dataset_summary

        base_df = _make_base_df(80)
        base_df.to_parquet(tmp_store._base_parquet, index=False)
        tmp_store._update_manifest_from_base()

        inc_df = _make_increment_df(25)
        tmp_store.append(inc_df, "2017-10")

        # Patch the store singleton
        original = dataset_summary._cumulative_store
        dataset_summary._cumulative_store = tmp_store
        try:
            from fastapi import FastAPI
            app = FastAPI()
            app.include_router(dataset_summary.router)
            client = TestClient(app)
            resp = client.get("/dataset/coverage")
            assert resp.status_code == 200
            data = resp.json()
            assert data["combined_total"] == 105
            assert data["increment_count"] == 1
        finally:
            dataset_summary._cumulative_store = original

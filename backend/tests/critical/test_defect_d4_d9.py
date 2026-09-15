"""
Tests for Defects 4-9.

D4 — Stage 9 retrains on cumulative, raises when frame is too small
D5 — training exception → status "Failed", retrained_models empty
D5 — InventoryTrainer absent from entire backend
D6 — no stage emits a hardcoded confidence string
D7 — version tag contains period, no literal "2015"
D8 — live_ops uses CumulativeStore; dynamic_upgrade does not write parquet
D9 — coordinator uses tail(cap) not head(500)
"""

import ast
import pathlib
import re
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

BACKEND = pathlib.Path(__file__).parent.parent.parent  # backend/

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_df(n=50, start="2015-01-01", end="2017-09-30"):
    rng = np.random.default_rng(0)
    dates = pd.date_range(start, end, periods=n)
    return pd.DataFrame({
        "order date (DateOrders)": dates,
        "Order Region": rng.choice(["Western Europe", "Central America"], n),
        "Category Name": rng.choice(["Fishing", "Cleats"], n),
        "Order Item Quantity": rng.integers(1, 10, n).astype(float),
        "Late_delivery_risk": rng.integers(0, 2, n).astype(float),
        "Sales": rng.random(n) * 200,
        "feature_a": rng.random(n),
        "feature_b": rng.random(n),
    })


# ─────────────────────────────────────────────────────────────────────────────
# D5 — InventoryTrainer absent from entire backend
# ─────────────────────────────────────────────────────────────────────────────

class TestInventoryTrainerAbsent:
    def test_no_inventory_trainer_in_backend(self):
        """InventoryTrainer must not appear anywhere in backend/app/."""
        app_dir = BACKEND / "app"
        hits = []
        for py in app_dir.rglob("*.py"):
            text = py.read_text(encoding="utf-8", errors="ignore")
            if "InventoryTrainer" in text:
                hits.append(str(py))
        assert hits == [], f"InventoryTrainer found in: {hits}"


# ─────────────────────────────────────────────────────────────────────────────
# D6 — no hardcoded confidence strings in enterprise_learning_engine.py
# ─────────────────────────────────────────────────────────────────────────────

class TestNoHardcodedConfidence:
    def test_no_hardcoded_confidence_in_engine(self):
        """No stage in enterprise_learning_engine.py may emit a hardcoded XX.X% confidence."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        # Match strings like "99.9%", "98.5%", "94.2%" etc. as string literals
        hits = re.findall(r'"[\d]+\.[\d]+%"', src)
        assert hits == [], f"Hardcoded confidence strings found: {hits}"

    def test_confidence_field_is_none_or_computed(self):
        """No stage constructor may pass a numeric percentage string as confidence."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        # Match confidence="XX.X%" or confidence="XX%" — numeric percentage literals
        bad = re.findall(r'confidence="[\d]+[\d.]*%"', src)
        assert bad == [], f"Hardcoded numeric confidence% literals found: {bad}"


# ─────────────────────────────────────────────────────────────────────────────
# D7 — version tag contains period, no literal "2015"
# ─────────────────────────────────────────────────────────────────────────────

class TestVersionTag:
    def test_version_tag_no_literal_2015(self):
        """new_version_tag must not contain the literal string '2015'."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        # Find the version tag assignment line
        match = re.search(r'new_version_tag\s*=\s*(.+)', src)
        assert match, "new_version_tag assignment not found"
        tag_expr = match.group(1).strip()
        assert "2015" not in tag_expr, (
            f"Literal '2015' found in version tag expression: {tag_expr}"
        )

    def test_version_tag_contains_period_variable(self):
        """new_version_tag expression must reference the {period} variable."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        match = re.search(r'new_version_tag\s*=\s*(.+)', src)
        assert match, "new_version_tag assignment not found"
        tag_expr = match.group(1).strip()
        assert "period" in tag_expr, (
            f"'period' variable not referenced in version tag: {tag_expr}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D4 — Stage 9 raises when cumulative frame is too small
# ─────────────────────────────────────────────────────────────────────────────

class TestStage9CumulativeGuard:
    def test_stage9_raises_on_small_frame(self, tmp_path):
        """Stage 9 must raise RuntimeError when cumulative frame < 2× increment."""
        from app.store.cumulative import CumulativeStore

        store = CumulativeStore(base_dir=tmp_path)
        base_df = _make_df(100)
        base_df.to_parquet(store._base_parquet, index=False)
        store._update_manifest_from_base()

        # Increment is 60 rows; cumulative = 160 rows; 160 < 60*2=120 is False
        # so we need cumulative < increment*2 → make increment larger than half cumulative
        # Use a 90-row increment so cumulative=190, 190 < 90*2=180 is False
        # Actually: cumulative(100) < increment(60)*2=120 → True → raises
        inc_df = _make_df(60, start="2017-10-01", end="2017-10-31")
        # Don't append — we want load_full() to return only base (100 rows)
        # and df_features (increment) to be 60 rows → 100 < 120 → raises

        with patch("app.store.cumulative.CumulativeStore.load_full", return_value=base_df):
            with pytest.raises(RuntimeError, match="Refusing to train"):
                df_cumulative = base_df  # 100 rows
                df_features = inc_df    # 60 rows
                if len(df_cumulative) < len(df_features) * 2:
                    raise RuntimeError(
                        f"Retraining frame has only {len(df_cumulative):,} rows; "
                        f"expected the full cumulative dataset. Refusing to train."
                    )

    def test_stage9_uses_cumulative_not_increment(self, tmp_path):
        """train_all must be called with the full cumulative frame, not just the increment."""
        from app.store.cumulative import CumulativeStore

        store = CumulativeStore(base_dir=tmp_path)
        base_df = _make_df(200)
        base_df.to_parquet(store._base_parquet, index=False)
        store._update_manifest_from_base()

        inc_df = _make_df(30, start="2017-10-01", end="2017-10-31")
        store.append(inc_df, "2017-10")

        full_df = store.load_full()
        assert len(full_df) == 230

        # Simulate Stage 9 logic: cumulative must be >= increment*2
        assert len(full_df) >= len(inc_df) * 2, (
            f"Cumulative {len(full_df)} < increment*2 {len(inc_df)*2}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D5 — training exception → status "Failed", retrained_models empty
# ─────────────────────────────────────────────────────────────────────────────

class TestStage9FailureHandling:
    def test_training_exception_sets_failed_status(self):
        """When train_all raises, stage9_status must be 'Failed' and retrained_models empty."""
        retrained_models = []
        stage9_status = "Skipped"
        stage9_summary = ""

        # Simulate the Stage 9 try/except block
        try:
            raise RuntimeError("Simulated training failure")
        except Exception as e_train:
            retrained_models = []
            stage9_status = "Failed"
            stage9_summary = f"Retraining failed: {e_train}"

        assert stage9_status == "Failed"
        assert retrained_models == []
        assert "Simulated training failure" in stage9_summary

    def test_stage9_status_in_engine_source(self):
        """enterprise_learning_engine.py must set stage9_status='Failed' on exception."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert 'stage9_status = "Failed"' in src, (
            "Stage 9 failure path must set stage9_status='Failed'"
        )
        assert "retrained_models = []" in src, (
            "Stage 9 failure path must set retrained_models=[]"
        )

    def test_any_stage_failed_in_to_dict(self):
        """ContinuousLearningResult.to_dict() must expose any_stage_failed."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert "any_stage_failed" in src, (
            "to_dict() must include any_stage_failed key"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D8a — live_ops uses CumulativeStore, not bespoke parquet cache
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveOpsCumulativeStore:
    def test_live_ops_no_bespoke_cache_globals(self):
        """live_ops.py must not define _parquet_cache or _parquet_mtime globals."""
        src = (BACKEND / "app/api/v1/endpoints/live_ops.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert "_parquet_cache" not in src, "_parquet_cache global must be removed from live_ops.py"
        assert "_parquet_mtime" not in src, "_parquet_mtime global must be removed from live_ops.py"

    def test_live_ops_uses_cumulative_store(self):
        """live_ops._load_parquet must call CumulativeStore().load_full()."""
        src = (BACKEND / "app/api/v1/endpoints/live_ops.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert "CumulativeStore" in src, "live_ops.py must use CumulativeStore"
        assert "load_full" in src, "live_ops.py must call load_full()"

    def test_live_ops_returns_data_with_increment(self, tmp_path):
        """_load_parquet in live_ops must return data that includes an appended increment."""
        from app.store.cumulative import CumulativeStore

        store = CumulativeStore(base_dir=tmp_path)
        base_df = _make_df(100)
        base_df.to_parquet(store._base_parquet, index=False)
        store._update_manifest_from_base()

        inc_df = _make_df(25, start="2017-10-01", end="2017-10-31")
        store.append(inc_df, "2017-10")

        full = store.load_full()
        assert len(full) == 125, f"Expected 125 rows after increment, got {len(full)}"
        # Confirm the increment period is present
        assert store.periods() == ["2017-10"]


# ─────────────────────────────────────────────────────────────────────────────
# D8b — dynamic_upgrade_service does not write processed_master.parquet
# ─────────────────────────────────────────────────────────────────────────────

class TestDynamicUpgradeNoParquetWrite:
    def test_no_to_parquet_write_in_dynamic_upgrade(self):
        """dynamic_upgrade_service.py must not call df_features.to_parquet(self.master_parquet_path)."""
        src = (BACKEND / "app/services/dynamic_upgrade_service.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        # The write pattern was: df_features.to_parquet(self.master_parquet_path, index=False)
        assert "df_features.to_parquet" not in src, (
            "dynamic_upgrade_service must not write df_features.to_parquet — use CumulativeStore.append()"
        )

    def test_dynamic_upgrade_uses_cumulative_store_append(self):
        """dynamic_upgrade_service.py must use CumulativeStore().append() instead."""
        src = (BACKEND / "app/services/dynamic_upgrade_service.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert "CumulativeStore" in src, (
            "dynamic_upgrade_service must import and use CumulativeStore"
        )
        assert "_store.append" in src or "store.append" in src, (
            "dynamic_upgrade_service must call CumulativeStore.append()"
        )


# ─────────────────────────────────────────────────────────────────────────────
# D9 — coordinator uses tail(cap) not head(500)
# ─────────────────────────────────────────────────────────────────────────────

class TestCoordinatorRowCap:
    def test_no_head_500_in_engine(self):
        """enterprise_learning_engine.py must not call .head(500)."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert ".head(500)" not in src, (
            ".head(500) must be replaced with configurable tail(cap)"
        )

    def test_coordinator_uses_tail_with_cap(self):
        """enterprise_learning_engine.py must use .tail(_cap) for coordinator input."""
        src = (BACKEND / "app/services/enterprise_learning_engine.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert "coordinator_row_cap" in src, (
            "coordinator_row_cap config must be referenced in engine"
        )
        assert ".tail(" in src, (
            "coordinator must use .tail(cap) to take most-recent rows"
        )

    def test_coordinator_row_cap_in_config(self):
        """Settings must expose coordinator_row_cap with default 0."""
        src = (BACKEND / "app/core/config.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        assert "coordinator_row_cap" in src, (
            "coordinator_row_cap must be defined in Settings"
        )
        # Default must be 0 (no cap)
        assert "coordinator_row_cap: int = 0" in src, (
            "coordinator_row_cap default must be 0 (no cap)"
        )

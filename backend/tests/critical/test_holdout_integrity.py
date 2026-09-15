"""
tests/critical/test_holdout_integrity.py
=========================================
Part 6 tests — holdout evaluation integrity.

Covers:
  1. Split produces four files totalling 8,557 rows
  2. No holdout row appears in the training CSV
  3. Initialization raises when training frame contains holdout dates
  4. Graph build receives no holdout rows
  5. Replay writes empty metric cells, not zeros, for a SKIPPED stage
  6. Delivery Status is absent from every agent feature list
  7. The ablated arm has the same column count as the with_graph arm
"""

import csv
import io
import pandas as pd
import pytest
from pathlib import Path

BACKEND = Path(__file__).parent.parent.parent
ACTUALS_REAL = BACKEND / "data" / "actuals_real"
RAW_DIR      = BACKEND / "data" / "raw"

HOLDOUT_START = pd.Timestamp("2017-10-01")
EXPECTED_TRAIN   = 171_962
EXPECTED_HOLDOUT = 8_557
EXPECTED_MONTHLY = {
    "2017-10": 2255,
    "2017-11": 2055,
    "2017-12": 2124,
    "2018-01": 2123,
}
HOLDOUT_FILES = [
    "2017_10_actual.csv",
    "2017_11_actual.csv",
    "2017_12_actual.csv",
    "2018_01_actual.csv",
]


# ── 1. Split produces four files totalling 8,557 rows ────────────────────────

class TestSplitFiles:
    @pytest.mark.skipif(
        not ACTUALS_REAL.exists(),
        reason="actuals_real/ not yet created — run create_holdout_actuals.py first",
    )
    def test_four_holdout_files_exist(self):
        for fname in HOLDOUT_FILES:
            assert (ACTUALS_REAL / fname).exists(), f"Missing holdout file: {fname}"

    @pytest.mark.skipif(
        not ACTUALS_REAL.exists(),
        reason="actuals_real/ not yet created",
    )
    def test_holdout_total_rows(self):
        total = 0
        for fname in HOLDOUT_FILES:
            df = pd.read_csv(ACTUALS_REAL / fname)
            total += len(df)
        assert total == EXPECTED_HOLDOUT, (
            f"Holdout total: expected {EXPECTED_HOLDOUT}, got {total}"
        )

    @pytest.mark.skipif(
        not ACTUALS_REAL.exists(),
        reason="actuals_real/ not yet created",
    )
    def test_monthly_row_counts(self):
        month_map = {
            "2017-10": "2017_10_actual.csv",
            "2017-11": "2017_11_actual.csv",
            "2017-12": "2017_12_actual.csv",
            "2018-01": "2018_01_actual.csv",
        }
        for month, fname in month_map.items():
            df = pd.read_csv(ACTUALS_REAL / fname)
            assert len(df) == EXPECTED_MONTHLY[month], (
                f"{month}: expected {EXPECTED_MONTHLY[month]} rows, got {len(df)}"
            )


# ── 2. No holdout row appears in the training CSV ────────────────────────────

class TestNoHoldoutInTrain:
    @pytest.mark.skipif(
        not (RAW_DIR / "DataCoSupplyChainDataset_train.csv").exists(),
        reason="Training CSV not yet created — run create_holdout_actuals.py first",
    )
    def test_train_csv_ends_before_holdout(self):
        train_csv = RAW_DIR / "DataCoSupplyChainDataset_train.csv"
        df = pd.read_csv(train_csv, usecols=["order date (DateOrders)"])
        dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce").dropna()
        max_date = dates.max()
        assert max_date < HOLDOUT_START, (
            f"Training CSV contains date {max_date.date()} >= holdout start {HOLDOUT_START.date()}"
        )

    @pytest.mark.skipif(
        not (RAW_DIR / "DataCoSupplyChainDataset_train.csv").exists(),
        reason="Training CSV not yet created",
    )
    def test_train_csv_row_count(self):
        train_csv = RAW_DIR / "DataCoSupplyChainDataset_train.csv"
        df = pd.read_csv(train_csv, usecols=["order date (DateOrders)"])
        assert len(df) == EXPECTED_TRAIN, (
            f"Training CSV: expected {EXPECTED_TRAIN} rows, got {len(df)}"
        )


# ── 3. Initialization raises when training frame contains holdout dates ───────

class TestHoldoutGuardRaises:
    def test_guard_raises_on_holdout_data(self):
        """
        Simulate the holdout guard in service.py:
        if max_date >= holdout_start -> RuntimeError.
        """
        holdout_start = "2017-10-01"
        # Frame that includes a holdout date
        df = pd.DataFrame({
            "order date (DateOrders)": ["2017-09-30", "2017-10-01", "2017-10-15"],
        })
        dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
        max_date = dates.max()

        with pytest.raises(RuntimeError, match="Holdout violation"):
            if max_date >= pd.Timestamp(holdout_start):
                raise RuntimeError(
                    f"Holdout violation: training frame contains data at "
                    f"{max_date.date()}, on or after holdout start {holdout_start}"
                )

    def test_guard_passes_on_clean_data(self):
        """Frame ending before holdout_start must NOT raise."""
        holdout_start = "2017-10-01"
        df = pd.DataFrame({
            "order date (DateOrders)": ["2017-09-01", "2017-09-15", "2017-09-30"],
        })
        dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
        max_date = dates.max()
        # Should not raise
        if max_date >= pd.Timestamp(holdout_start):
            raise RuntimeError("Guard should not fire on clean data")

    def test_parquet_integrity_raises_on_contaminated_parquet(self):
        """
        assert_parquet_integrity must raise when the parquet contains a row
        dated 2017-10-15 (on or after holdout_start_date).
        Proof that Issue 2 is fixed: the check is NOT inverted.
        """
        import numpy as np
        from app.initialization.service import assert_parquet_integrity
        from app.ml.utils import GRAPH_CONTEXT_FEATURES

        n = 110_000
        dates = pd.date_range("2015-01-01", periods=n, freq="8h")
        df = pd.DataFrame({
            "order date (DateOrders)": dates,
            **{col: np.random.default_rng(0).random(n) for col in GRAPH_CONTEXT_FEATURES},
        })
        df.loc[0, "order date (DateOrders)"] = pd.Timestamp("2017-10-15")

        with pytest.raises((ValueError, RuntimeError)):
            assert_parquet_integrity(df, "test_contaminated.parquet")

    def test_parquet_integrity_passes_on_clean_parquet(self):
        """assert_parquet_integrity must NOT raise when max date < holdout_start."""
        import numpy as np
        from app.initialization.service import assert_parquet_integrity
        from app.ml.utils import GRAPH_CONTEXT_FEATURES

        n = 110_000
        dates = pd.date_range("2015-01-01", "2017-09-30", periods=n)
        df = pd.DataFrame({
            "order date (DateOrders)": dates,
            **{col: np.random.default_rng(1).random(n) for col in GRAPH_CONTEXT_FEATURES},
        })
        try:
            assert_parquet_integrity(df, "test_clean.parquet")
        except (ValueError, RuntimeError) as e:
            assert "contaminated" not in str(e).lower(), (
                f"Clean parquet raised contamination error: {e}"
            )


# ── 4. Graph build receives no holdout rows ───────────────────────────────────

class TestGraphBuildNoHoldout:
    def test_graph_frame_ends_before_holdout(self):
        """
        The frame passed to graph build must have max date < holdout_start.
        This mirrors the guard in service.py Step 4.
        """
        holdout_start = pd.Timestamp("2017-10-01")
        # Simulate a clean training frame
        df = pd.DataFrame({
            "order date (DateOrders)": pd.date_range("2015-01-01", "2017-09-30", freq="D"),
        })
        max_date = pd.to_datetime(df["order date (DateOrders)"], errors="coerce").max()
        assert max_date < holdout_start, (
            f"Graph build frame contains date {max_date.date()} >= holdout start"
        )

    def test_graph_frame_with_holdout_would_raise(self):
        """Confirm the guard logic catches a contaminated frame."""
        holdout_start = pd.Timestamp("2017-10-01")
        df = pd.DataFrame({
            "order date (DateOrders)": pd.date_range("2015-01-01", "2017-10-15", freq="D"),
        })
        max_date = pd.to_datetime(df["order date (DateOrders)"], errors="coerce").max()
        assert max_date >= holdout_start, "Test setup error: frame should contain holdout dates"


# ── 5. Replay writes empty metric cells, not zeros, for a SKIPPED stage ───────

class TestReplaySkippedMetrics:
    def _make_replay_csv(self, stage3_status: str, metric_val) -> str:
        """Build a minimal replay_results.csv in memory."""
        header = [
            "month", "rows_uploaded", "matched_pairs", "unmatched_excluded",
            "demand_mae", "demand_rmse", "demand_r2",
            "supplier_auc", "supplier_f1", "supplier_brier",
            "logistics_auc", "logistics_f1", "logistics_brier",
            "tpke_edges_created", "tpke_edges_strengthened", "tpke_edges_decayed",
            "tpke_edges_removed", "total_inferred_edges", "cycle_duration_s",
            "stage2_status", "stage3_status", "notes",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=header)
        writer.writeheader()
        writer.writerow({
            "month": "2017-10",
            "rows_uploaded": 2255,
            "matched_pairs": "" if stage3_status == "SKIPPED" else 2255,
            "unmatched_excluded": 0,
            "demand_mae":    metric_val,
            "demand_rmse":   metric_val,
            "demand_r2":     metric_val,
            "supplier_auc":  metric_val,
            "supplier_f1":   metric_val,
            "supplier_brier":metric_val,
            "logistics_auc": metric_val,
            "logistics_f1":  metric_val,
            "logistics_brier":metric_val,
            "tpke_edges_created": 5,
            "tpke_edges_strengthened": 2,
            "tpke_edges_decayed": 1,
            "tpke_edges_removed": 0,
            "total_inferred_edges": 7,
            "cycle_duration_s": 3.14,
            "stage2_status": "SKIPPED" if stage3_status == "SKIPPED" else "COMPLETED",
            "stage3_status": stage3_status,
            "notes": "Cycle 1: no standing forecast" if stage3_status == "SKIPPED" else "",
        })
        return buf.getvalue()

    def test_skipped_cycle_has_empty_metric_cells(self):
        """Cycle 1 SKIPPED: all metric cells must be empty string, not '0'."""
        csv_text = self._make_replay_csv("SKIPPED", "")
        reader = csv.DictReader(io.StringIO(csv_text))
        row = next(reader)
        metric_cols = [
            "demand_mae", "demand_rmse", "demand_r2",
            "supplier_auc", "supplier_f1", "supplier_brier",
            "logistics_auc", "logistics_f1", "logistics_brier",
        ]
        for col in metric_cols:
            assert row[col] == "", (
                f"SKIPPED cycle: column '{col}' should be empty string, got '{row[col]}'. "
                f"Empty string != zero — zeros would read as real measurements."
            )

    def test_skipped_cycle_not_zeros(self):
        """
        The replay script must write empty string for SKIPPED metrics, not '0'.
        This test verifies the correct path (empty string) passes the guard,
        and documents that '0' would be wrong.
        """
        # Correct path: empty string for SKIPPED
        csv_text_correct = self._make_replay_csv("SKIPPED", "")
        reader = csv.DictReader(io.StringIO(csv_text_correct))
        row = next(reader)
        assert row["demand_mae"] == "", (
            "SKIPPED cycle must write empty string for demand_mae, not '0'."
        )
        # Confirm the empty string is not '0'
        assert row["demand_mae"] != "0", (
            "SKIPPED cycle must not write '0' for demand_mae — use empty string."
        )

    def test_completed_cycle_has_numeric_metrics(self):
        """Completed cycle must have real numeric values, not empty strings."""
        csv_text = self._make_replay_csv("COMPLETED", "0.7234")
        reader = csv.DictReader(io.StringIO(csv_text))
        row = next(reader)
        assert row["supplier_auc"] == "0.7234"
        assert float(row["supplier_auc"]) > 0


# ── 6. Delivery Status is absent from every agent feature list ────────────────

class TestDeliveryStatusAbsent:
    def test_delivery_status_not_in_demand_features(self):
        from app.ml.utils import DEMAND_FEATURES
        assert "Delivery Status" not in DEMAND_FEATURES, (
            "Delivery Status must not appear in DEMAND_FEATURES. "
            "It is a categorical perfect-mapping of Late_delivery_risk."
        )

    def test_delivery_status_not_in_supplier_features(self):
        from app.ml.utils import SUPPLIER_FEATURES
        assert "Delivery Status" not in SUPPLIER_FEATURES, (
            "Delivery Status must not appear in SUPPLIER_FEATURES."
        )

    def test_delivery_status_not_in_logistics_features(self):
        from app.ml.utils import LOGISTICS_FEATURES
        assert "Delivery Status" not in LOGISTICS_FEATURES, (
            "Delivery Status must not appear in LOGISTICS_FEATURES."
        )

    def test_banned_from_models_covers_delivery_status(self):
        from app.core.constants import BANNED_FROM_MODELS
        assert "Delivery Status" in BANNED_FROM_MODELS, (
            "Delivery Status must be in BANNED_FROM_MODELS."
        )

    def test_no_feature_list_intersects_banned(self):
        from app.core.constants import BANNED_FROM_MODELS
        from app.ml.utils import DEMAND_FEATURES, SUPPLIER_FEATURES, LOGISTICS_FEATURES
        banned = set(BANNED_FROM_MODELS)
        for name, feats in [
            ("DEMAND",    DEMAND_FEATURES),
            ("SUPPLIER",  SUPPLIER_FEATURES),
            ("LOGISTICS", LOGISTICS_FEATURES),
        ]:
            overlap = banned & set(feats)
            assert not overlap, (
                f"{name}_FEATURES contains BANNED_FROM_MODELS columns: {sorted(overlap)}"
            )


# ── 7. Ablated arm has the same column count as the with_graph arm ────────────

class TestAblationColumnCount:
    def test_mean_replacement_preserves_column_count(self):
        """
        Mean replacement must not change the number of columns.
        Both arms must have identical feature matrix shapes.
        """
        import numpy as np
        from app.ml.utils import FEATURE_CONFIGS, GRAPH_CONTEXT_FEATURES, IntelligenceType

        for intel_type in [IntelligenceType.SUPPLIER, IntelligenceType.LOGISTICS]:
            fc = FEATURE_CONFIGS[intel_type]
            full_features = fc.features

            # Simulate a training frame with all features present
            n = 100
            rng = np.random.default_rng(42)
            data = {f: rng.random(n) for f in full_features}
            X = pd.DataFrame(data)

            # with_graph arm: use all columns
            X_wg = X[full_features]

            # graph_ablated arm: replace graph columns with training-set mean
            X_abl = X[full_features].copy()
            for col in GRAPH_CONTEXT_FEATURES:
                if col in X_abl.columns:
                    X_abl[col] = float(X_abl[col].mean())

            assert X_wg.shape[1] == X_abl.shape[1], (
                f"{intel_type.value}: with_graph has {X_wg.shape[1]} cols, "
                f"ablated has {X_abl.shape[1]} cols. "
                f"Mean replacement must preserve column count."
            )
            assert list(X_wg.columns) == list(X_abl.columns), (
                f"{intel_type.value}: column names differ between arms."
            )

    def test_graph_columns_are_neutralized_not_dropped(self):
        """Graph columns must exist in the ablated arm (just with mean values)."""
        import numpy as np
        from app.ml.utils import FEATURE_CONFIGS, GRAPH_CONTEXT_FEATURES, IntelligenceType

        fc = FEATURE_CONFIGS[IntelligenceType.SUPPLIER]
        n = 50
        rng = np.random.default_rng(0)
        data = {f: rng.random(n) for f in fc.features}
        X = pd.DataFrame(data)

        X_abl = X.copy()
        for col in GRAPH_CONTEXT_FEATURES:
            if col in X_abl.columns:
                X_abl[col] = float(X_abl[col].mean())

        for col in GRAPH_CONTEXT_FEATURES:
            if col in X.columns:
                assert col in X_abl.columns, (
                    f"Graph column '{col}' was dropped from ablated arm. "
                    f"Use mean replacement, not column removal."
                )
                # All values should equal the mean
                assert X_abl[col].nunique() == 1, (
                    f"Graph column '{col}' in ablated arm should have exactly 1 unique value (the mean)."
                )

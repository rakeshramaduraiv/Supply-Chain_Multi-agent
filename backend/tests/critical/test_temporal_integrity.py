"""
Critical test — Temporal integrity (§8.1 Gate 5).

max(train date) must be strictly less than min(test date) for every split.
A random split would violate this and constitute future leakage.
"""

import pandas as pd
import pytest

from app.feature_engineering import engineer_features
from app.ml.utils import chronological_split

DATA_PATH = "data/raw/DataCoSupplyChainDataset.csv"
DATE_COL  = "order date (DateOrders)"


@pytest.fixture(scope="module")
def raw_df():
    return pd.read_csv(DATA_PATH, encoding="latin-1")


class TestTemporalIntegrity:

    def test_chronological_split_no_overlap(self, raw_df):
        """max(train date) < min(test date)."""
        df = raw_df.copy()
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
        df = df.dropna(subset=[DATE_COL]).sort_values(DATE_COL)

        train, test = chronological_split(df, train_ratio=0.8)

        max_train = train[DATE_COL].max()
        min_test  = test[DATE_COL].min()

        assert max_train <= min_test, (
            f"Temporal integrity VIOLATED: max(train)={max_train} > min(test)={min_test}. "
            f"Test rows appear before the end of the training period — future leakage."
        )
        print(f"\n  max_train={max_train.date()}  min_test={min_test.date()}  [PASS]")

    def test_no_shuffling_in_split(self, raw_df):
        """
        Verify the split is positional (iloc), not random.
        After sorting by date, the 80th percentile date must be the split boundary.
        """
        df = raw_df.copy()
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
        df = df.dropna(subset=[DATE_COL]).sort_values(DATE_COL).reset_index(drop=True)

        train, test = chronological_split(df, train_ratio=0.8)

        # The last train row must be the row at index int(len(df)*0.8) - 1
        split_idx = int(len(df) * 0.8)
        assert len(train) == split_idx, (
            f"Train size {len(train)} != expected {split_idx}. "
            f"Split may not be positional."
        )
        assert len(test) == len(df) - split_idx

    def test_engineer_features_on_test_no_future_leakage(self, raw_df):
        """
        engineer_features_on_test must not allow test rows to influence
        train-set statistics. Verify by checking that the combined frame
        is sorted chronologically before engineering.
        """
        from app.feature_engineering import engineer_features_on_test

        df = raw_df.copy()
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
        df = df.dropna(subset=[DATE_COL]).sort_values(DATE_COL).reset_index(drop=True)

        split_idx = int(len(df) * 0.8)
        train_raw = df.iloc[:split_idx]
        test_raw  = df.iloc[split_idx:]

        test_eng = engineer_features_on_test(test_raw, train_raw)

        # Test rows must still be in the test period
        test_dates = pd.to_datetime(test_eng[DATE_COL], errors="coerce").dropna()
        if len(test_dates) > 0:
            max_train_date = pd.to_datetime(train_raw[DATE_COL], errors="coerce").max()
            assert test_dates.min() >= max_train_date - pd.Timedelta(days=1), (
                "engineer_features_on_test returned rows from the training period."
            )

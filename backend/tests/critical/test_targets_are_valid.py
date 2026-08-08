"""
Critical test — Every classification target has 2 classes, minority > 1% (§8.1 Gate 3).

A 1×1 confusion matrix (single-class target) means the model predicts a constant.
roc_auc: NaN confirms it. This test catches that before training.
"""

import pandas as pd
import pytest

from app.feature_engineering import engineer_features
from app.ml.utils import (
    FEATURE_CONFIGS, IntelligenceType, ModelTask, build_stockout_target,
)

DATA_PATH = "data/raw/DataCoSupplyChainDataset.csv"


@pytest.fixture(scope="module")
def engineered_df():
    df_raw = pd.read_csv(DATA_PATH, encoding="latin-1")
    return engineer_features(df_raw)


class TestTargetValidity:

    def test_late_delivery_risk_two_classes(self, engineered_df):
        target = "Late_delivery_risk"
        assert target in engineered_df.columns, f"{target} missing"
        vc = engineered_df[target].value_counts(normalize=True)
        assert len(vc) == 2, (
            f"{target} has {len(vc)} class(es) — must have exactly 2"
        )
        minority = float(vc.min())
        assert minority >= 0.05, (
            f"{target} minority class = {minority:.3f} < 5%. "
            f"Model will predict the majority class only."
        )
        print(f"\n  Late_delivery_risk: minority={minority:.3f}  [PASS]")

    def test_stockout_flag_two_classes(self, engineered_df):
        target = build_stockout_target(engineered_df)
        vc = target.value_counts(normalize=True)
        assert len(vc) == 2, (
            f"stockout_risk_flag has {len(vc)} class(es) — must have exactly 2. "
            f"Check days_until_reorder formula."
        )
        minority = float(vc.min())
        assert minority >= 0.01, (
            f"stockout_risk_flag minority = {minority:.3f} < 1%. "
            f"scale_pos_weight=3 cannot compensate for this imbalance."
        )
        print(f"\n  stockout_risk_flag: minority={minority:.3f}  [PASS]")

    @pytest.mark.parametrize("agent_type", [
        IntelligenceType.SUPPLIER,
        IntelligenceType.LOGISTICS,
        IntelligenceType.INVENTORY,
    ])
    def test_classification_target_not_single_class(self, engineered_df, agent_type):
        config = FEATURE_CONFIGS[agent_type]
        if config.task != ModelTask.CLASSIFICATION:
            pytest.skip(f"{agent_type.value} is a regressor")

        if config.target == "stockout_risk_flag":
            target = build_stockout_target(engineered_df)
        else:
            assert config.target in engineered_df.columns, (
                f"Target '{config.target}' missing from engineered DataFrame"
            )
            target = engineered_df[config.target]

        n_classes = target.nunique()
        assert n_classes == 2, (
            f"{agent_type.value} target '{config.target}' has {n_classes} unique values. "
            f"A single-class target produces a degenerate model."
        )

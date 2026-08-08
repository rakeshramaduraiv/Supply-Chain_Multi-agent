"""
Critical test — No target leakage in any agent (§8.1 Gate 1 & 2).

Checks:
  1. Blacklisted features absent from all feature lists (import-time guard)
  2. Statistical audit: max |Pearson(feature, target)| < 0.85 on real data
  3. Expanding-rate features used instead of full-df encodings
"""

import numpy as np
import pandas as pd
import pytest

from app.feature_engineering import engineer_features
from app.ml.utils import (
    DEMAND_FEATURES, INVENTORY_FEATURES, SUPPLIER_FEATURES, LOGISTICS_FEATURES,
    FEATURE_CONFIGS, IntelligenceType, prepare_features, audit_feature_leakage,
)

DATA_PATH = "data/raw/DataCoSupplyChainDataset.csv"

# Hard blacklist — these must never appear in any late-delivery model
HARD_BLACKLIST = {
    "is_delayed",
    "shipping_delay_ratio",
    "shipping_efficiency_score",
    "delivery_duration_days",
    "Days for shipping (real)",
    "delivery_gap",
    "delay_category",
    "supplier_delay_rate",   # full-df target encoding
}

# Full-df encodings that must be replaced by expanding rates
FULL_DF_ENCODINGS = {
    "supplier_delay_rate",
    "region_congestion_index",  # old full-df version
}


class TestBlacklist:
    """Gate 1: No blacklisted feature in any model."""

    @pytest.mark.parametrize("name,features", [
        ("SUPPLIER",  SUPPLIER_FEATURES),
        ("LOGISTICS", LOGISTICS_FEATURES),
        ("INVENTORY", INVENTORY_FEATURES),
    ])
    def test_no_blacklisted_feature(self, name, features):
        hits = HARD_BLACKLIST & set(features)
        assert not hits, (
            f"{name}_FEATURES contains blacklisted features: {sorted(hits)}. "
            f"These are post-shipment observables that leak the target."
        )

    def test_demand_no_algebraic_leakage(self):
        demand_bans = {"demand_intensity", "quantity_zscore",
                       "revenue_per_unit", "Sales", "Order Item Total"}
        hits = demand_bans & set(DEMAND_FEATURES)
        assert not hits, (
            f"DEMAND_FEATURES contains algebraic transforms of the target: {sorted(hits)}"
        )

    def test_no_full_df_encoding_in_supplier(self):
        hits = FULL_DF_ENCODINGS & set(SUPPLIER_FEATURES)
        assert not hits, (
            f"SUPPLIER_FEATURES contains full-df target encodings: {sorted(hits)}. "
            f"Use expanding_target_rate instead."
        )

    def test_expanding_rate_features_present(self):
        """Verify the leak-free replacements are actually in the feature lists."""
        assert "supplier_hist_late_rate" in SUPPLIER_FEATURES, (
            "supplier_hist_late_rate missing from SUPPLIER_FEATURES. "
            "This is the expanding-rate replacement for supplier_delay_rate."
        )
        assert "route_hist_late_rate" in LOGISTICS_FEATURES, (
            "route_hist_late_rate missing from LOGISTICS_FEATURES."
        )


class TestStatisticalAudit:
    """Gate 2: Max feature-target correlation < 0.85 on real data."""

    @pytest.fixture(scope="class")
    def engineered_df(self):
        df_raw = pd.read_csv(DATA_PATH, encoding="latin-1")
        return engineer_features(df_raw)

    @pytest.mark.parametrize("agent_type", [
        IntelligenceType.SUPPLIER,
        IntelligenceType.LOGISTICS,
    ])
    def test_max_correlation_below_threshold(self, engineered_df, agent_type):
        config = FEATURE_CONFIGS[agent_type]
        X, y = prepare_features(engineered_df, config)

        # corr_threshold=0.85 (Pearson), mi_threshold=0.8 (raw MI bits)
        # is_delayed would score corr=1.0 and mi>>0.8 and be caught instantly.
        # days_scheduled has corr~0.37 and raw MI~0.3 — legitimate predictive power.
        try:
            rows = audit_feature_leakage(X, y, corr_threshold=0.85, mi_threshold=0.8)
        except ValueError as e:
            pytest.fail(str(e))

        max_corr = max((r.target_corr for r in rows), default=0.0)
        assert max_corr < 0.85, (
            f"{agent_type.value}: max feature-target correlation = {max_corr:.3f} >= 0.85. "
            f"A leak remains. Re-run audit_feature_leakage and inspect top features."
        )
        print(f"\n  {agent_type.value}: max_corr={max_corr:.4f}  [PASS]")

    def test_is_delayed_not_in_engineered_supplier_features(self, engineered_df):
        """is_delayed must not appear in the feature matrix passed to Supplier."""
        config = FEATURE_CONFIGS[IntelligenceType.SUPPLIER]
        X, _ = prepare_features(engineered_df, config)
        assert "is_delayed" not in X.columns, (
            "is_delayed appeared in Supplier feature matrix. "
            "This is a verbatim copy of Late_delivery_risk."
        )

    def test_shipping_delay_ratio_not_in_logistics_features(self, engineered_df):
        config = FEATURE_CONFIGS[IntelligenceType.LOGISTICS]
        X, _ = prepare_features(engineered_df, config)
        assert "shipping_delay_ratio" not in X.columns, (
            "shipping_delay_ratio appeared in Logistics feature matrix. "
            "This is a monotone transform of the target."
        )

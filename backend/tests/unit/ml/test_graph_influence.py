"""
Unit Test: Test Knowledge Graph Influence on Predictions
===========================================================
Verifies that passing healthy vs stressed Knowledge Graph context dicts
to PredictionEngine / DemandAgent results in measurably different predictions,
confirming the Knowledge Graph → GraphRAG → ML Agent bridge is active.
"""

import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from app.ml.prediction import PredictionEngine, DemandAgent
from app.ml.registry import ModelRegistry
from app.ml.training import BaseTrainer
from app.ml.utils import IntelligenceType
from app.feature_engineering import engineer_features


def _make_sample_raw_df(n_rows: int = 500) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2016-01-01", periods=n_rows, freq="D")
    return pd.DataFrame({
        "order date (DateOrders)": dates,
        "Order Item Quantity": np.random.randint(1, 15, n_rows),
        "Sales": np.random.uniform(50, 500, n_rows),
        "Product Price": np.random.uniform(20, 200, n_rows),
        "Order Item Discount": np.random.uniform(0, 0.2, n_rows),
        "Days for shipping (real)": np.random.randint(2, 6, n_rows),
        "Days for shipment (scheduled)": [4] * n_rows,
        "Late_delivery_risk": np.random.randint(0, 2, n_rows),
        "Category Name": np.random.choice(["Cleats", "Apparel", "Footwear"], n_rows),
        "Order Region": np.random.choice(["Western Europe", "Central America", "South Asia"], n_rows),
        "Shipping Mode": np.random.choice(["Standard Class", "First Class", "Same Day"], n_rows),
        "Department Name": np.random.choice(["Fan Shop", "Apparel", "Golf"], n_rows),
    })


def test_graph_influence_on_predictions():
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ModelRegistry(base_dir=Path(tmpdir))
        trainer = BaseTrainer(registry)
        raw_df = _make_sample_raw_df(500)
        df_eng = engineer_features(raw_df)

        # Train Demand model
        trainer.train(df_eng, IntelligenceType.DEMAND, run_walk_forward=False)

        ctx_healthy = {
            "avg_supplier_reliability": 0.95,
            "inventory_stress": 0.15,
            "avg_shipping_delay": 0.2,
            "demand_volatility": 0.1,
            "upcoming_events": [],
            "holiday_risk_events": [],
            "amplified_supplier_count": 0,
            "entities": [{}],
        }

        ctx_stressed = {
            "avg_supplier_reliability": 0.35,
            "inventory_stress": 0.88,
            "avg_shipping_delay": 6.5,
            "demand_volatility": 0.9,
            "upcoming_events": ["Festival Season"],
            "holiday_risk_events": ["Festival Season"],
            "amplified_supplier_count": 3,
            "entities": [{}],
        }

        d = DemandAgent(registry=registry)
        a = d.predict(df_eng.head(20), graph_context=ctx_healthy)
        b = d.predict(df_eng.head(20), graph_context=ctx_stressed)

        assert a.predictions != b.predictions, "FAIL: Knowledge Graph context has NO influence on predictions"
        print("PASS — Knowledge Graph measurably changes predictions.")

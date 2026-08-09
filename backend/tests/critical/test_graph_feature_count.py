"""
tests/critical/test_graph_feature_count.py
-------------------------------------------
Invariants for GRAPH_CONTEXT_FEATURES:

1. Exactly 3 active channels (graph_tpke_edge_density excluded until
   run_drift_experiment confirms real variance).

2. Every name in GRAPH_CONTEXT_FEATURES must also appear in
   _VARIANCE_CHECKED_COLS in app/graph/enrichment.py.
   A feature cannot be in the model input while exempt from the variance guard.
"""

from app.ml.utils import GRAPH_CONTEXT_FEATURES
from app.graph.enrichment import _VARIANCE_CHECKED_COLS


def test_graph_feature_count_is_three():
    assert len(GRAPH_CONTEXT_FEATURES) == 3, (
        f"Expected 3 active graph channels, got {len(GRAPH_CONTEXT_FEATURES)}: "
        f"{GRAPH_CONTEXT_FEATURES}. "
        f"graph_tpke_edge_density must not be re-added until run_drift_experiment "
        f"confirms nunique>100 and std>0.01."
    )


def test_all_graph_features_are_variance_checked():
    unchecked = [f for f in GRAPH_CONTEXT_FEATURES if f not in _VARIANCE_CHECKED_COLS]
    assert not unchecked, (
        f"These features are in GRAPH_CONTEXT_FEATURES but NOT in "
        f"_VARIANCE_CHECKED_COLS: {unchecked}. "
        f"A model input feature must never be exempt from the variance guard."
    )

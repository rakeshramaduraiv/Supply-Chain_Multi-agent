"""
tests/critical/test_enrichment_requires_neo4j.py
--------------------------------------------------
Asserts that enrich_graph_features_from_neo4j raises GraphContextUnavailable
when Neo4j returns no nodes — no pandas fallback path may exist.

This is the acceptance criterion stated in Q-1: if there is any path that
silently produces numbers without the graph, the same substitution will happen
again.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from app.graph.enrichment import GraphContextUnavailable, enrich_graph_features_from_neo4j


def _minimal_df() -> pd.DataFrame:
    """Cross-product DataFrame that clears _assert_anchor_cardinality so the
    test reaches the Neo4j fetch call."""
    import numpy as np
    rng = np.random.default_rng(42)
    rows = []
    for d in range(11):
        for c in range(50):
            for r in range(23):
                rows.append({
                    "Department Name":  f"Dept_{d}",
                    "Category Name":    f"Cat_{c}",
                    "Order Region":     f"Region_{r}",
                    "Shipping Mode":    f"Mode_{d % 4}",
                    "Order Country":    f"Country_{r % 30}",
                    "order date (DateOrders)": pd.Timestamp("2016-01-01") + pd.Timedelta(days=d*50+c+r),
                    "graph_supplier_reliability": float(rng.uniform(0.3, 0.9)),
                    "graph_inventory_stress":     float(rng.uniform(0.1, 0.8)),
                    "graph_avg_shipping_delay":   float(rng.uniform(-1.0, 3.0)),
                    "graph_tpke_edge_density":    float(rng.uniform(0.0, 0.5)),
                })
    return pd.DataFrame(rows)


def _make_conn() -> MagicMock:
    conn = MagicMock()
    conn.execute_query = AsyncMock(return_value=[])
    return conn


@pytest.mark.asyncio
async def test_enrichment_raises_when_neo4j_returns_empty():
    """
    When Neo4j returns no SupplierRoute nodes, enrichment must raise
    GraphContextUnavailable — not silently fall back to pandas.
    """
    df = _minimal_df()
    dates = pd.to_datetime(df["order date (DateOrders)"], errors="coerce")
    train_mask = dates <= dates.quantile(0.8)

    with pytest.raises(GraphContextUnavailable):
        await enrich_graph_features_from_neo4j(df, _make_conn(), train_mask)


def test_no_pandas_fallback_function_exists():
    """
    The module must not contain any _from_df fetch functions.
    Their presence indicates a silent fallback path exists.
    """
    import inspect
    import app.graph.enrichment as mod

    fallback_fns = [
        name for name, obj in inspect.getmembers(mod, inspect.isfunction)
        if name.endswith("_from_df")
    ]
    assert not fallback_fns, (
        f"Pandas fallback functions found in enrichment.py: {fallback_fns}. "
        f"Enrichment must raise when Neo4j is unavailable, not compute pandas aggregates."
    )

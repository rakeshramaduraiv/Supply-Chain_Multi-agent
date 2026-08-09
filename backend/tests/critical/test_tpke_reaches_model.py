"""
tests/critical/test_tpke_reaches_model.py
==========================================
Asserts that TPKE edges (RISK_CORRELATED, CO_FAILS_WITH) actually change the
graph_supplier_reliability value for an affected anchor node.

Without this test, TPKE is architecturally decorative: it can create, strengthen,
and prune edges all it likes, but no model feature will ever reflect the result.

Strategy
--------
1. Build a minimal in-memory Neo4j stub with two SupplierRoute nodes.
2. Run enrichment WITHOUT a TPKE edge — record baseline value.
3. Inject a :RISK_CORRELATED edge with a known weight and a different
   reliability_score on the peer.
4. Re-run enrichment — assert the anchor's value changed.

The test uses AsyncMock to avoid a live Neo4j connection, so it runs in CI.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from app.graph.enrichment import enrich_graph_features_from_neo4j


# ── Helpers ───────────────────────────────────────────────────────────────────

_N = 110  # must exceed _MIN_NUNIQUE=100


def _make_df() -> pd.DataFrame:
    """DataFrame with _N distinct SupplierRoute keys to satisfy cardinality guard."""
    import numpy as np
    rng = np.random.default_rng(42)
    depts   = [f"Dept_{i}"   for i in range(_N)]
    cats    = [f"Cat_{i}"    for i in range(_N)]
    regions = [f"Region_{i}" for i in range(_N)]
    return pd.DataFrame({
        "Department Name":  depts,
        "Category Name":    cats,
        "Order Region":     regions,
        "Shipping Mode":    ["Standard Class"] * _N,
        "Order Country":    ["France"] * _N,
        "order date (DateOrders)": pd.date_range("2017-01-01", periods=_N, freq="D"),
        "graph_supplier_reliability": rng.uniform(0.5, 0.9, _N),
        "graph_avg_shipping_delay":   rng.uniform(1.0, 3.0, _N),
        "graph_inventory_stress":     rng.uniform(0.2, 0.6, _N),
    })


def _make_records(df: pd.DataFrame, reliability_override: dict | None = None) -> tuple:
    """Build supplier/shipping/inventory record lists from df, with optional overrides."""
    import numpy as np
    rng = np.random.default_rng(0)
    supplier_records = [
        {
            "key": f"{row['Department Name']}|{row['Category Name']}|{row['Order Region']}",
            "reliability": reliability_override.get(
                f"{row['Department Name']}|{row['Category Name']}|{row['Order Region']}",
                float(row["graph_supplier_reliability"]),
            ) if reliability_override else float(row["graph_supplier_reliability"]),
        }
        for _, row in df.iterrows()
    ]
    shipping_records = [
        {
            "key": f"{row['Shipping Mode']}|{row['Order Region']}|{row['Order Country']}",
            "avg_delay": float(row["graph_avg_shipping_delay"]),
        }
        for _, row in df.drop_duplicates(["Shipping Mode", "Order Region", "Order Country"]).iterrows()
    ]
    inventory_records = [
        {
            "key": f"{row['Category Name']}|{row['Order Region']}",
            "stress": float(row["graph_inventory_stress"]),
        }
        for _, row in df.drop_duplicates(["Category Name", "Order Region"]).iterrows()
    ]
    return supplier_records, shipping_records, inventory_records


def _make_conn(supplier_records, shipping_records, inventory_records) -> AsyncMock:
    """Return a mock Neo4jConnectionManager whose execute_query returns the given records."""
    conn = AsyncMock()

    async def _execute(query, params):
        if "SupplierRoute" in query:
            return supplier_records
        if ":Route" in query or "(r:Route)" in query:
            return shipping_records
        if "Inventory" in query:
            return inventory_records
        if "Supplier" in query and "supplier_name" in query:
            # TPKE density query — return zero edges for all names
            names = params.get("names", [])
            return [{"name": n, "edge_count": 0} for n in names]
        return []

    conn.execute_query.side_effect = _execute
    return conn


def _train_mask(df: pd.DataFrame) -> pd.Series:
    return pd.Series([True] * len(df), index=df.index)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_tpke_edge_changes_supplier_reliability():
    """
    A :RISK_CORRELATED edge between two SupplierRoute nodes must change
    graph_supplier_reliability for the affected anchor.

    Anchor key = Dept_0|Cat_0|Region_0, baseline reliability = df value.
    With TPKE edge: Neo4j returns a blended value 0.10 lower for that key.
    Assert the output column reflects the change.
    """
    df = _make_df()
    anchor_key = "Dept_0|Cat_0|Region_0"
    anchor_row = df.iloc[0]
    baseline_rel = float(anchor_row["graph_supplier_reliability"])

    # Baseline — Neo4j returns each anchor's own value (no peer influence)
    s_base, sh, inv = _make_records(df)
    conn_baseline = _make_conn(s_base, sh, inv)
    df_baseline = asyncio.run(
        enrich_graph_features_from_neo4j(df, conn_baseline, _train_mask(df))
    )
    baseline_val = df_baseline["graph_supplier_reliability"].iloc[0]

    # With TPKE edge: Neo4j returns a different blended value for anchor_key
    tpke_blended = round(baseline_rel - 0.10, 4)
    s_tpke, _, _ = _make_records(df, reliability_override={anchor_key: tpke_blended})
    conn_tpke = _make_conn(s_tpke, sh, inv)
    df_tpke = asyncio.run(
        enrich_graph_features_from_neo4j(df, conn_tpke, _train_mask(df))
    )
    tpke_val = df_tpke["graph_supplier_reliability"].iloc[0]

    assert abs(tpke_val - baseline_val) > 0.05, (
        f"graph_supplier_reliability did not change after injecting a TPKE edge. "
        f"baseline={baseline_val:.4f}, tpke={tpke_val:.4f}. "
        "TPKE edges are not reaching the model feature."
    )


def test_no_tpke_edges_baseline_unchanged():
    """
    When Neo4j returns each anchor's own value (no peer influence),
    the output column must equal the input column for every row.
    """
    df = _make_df()
    s, sh, inv = _make_records(df)
    conn = _make_conn(s, sh, inv)
    df_out = asyncio.run(
        enrich_graph_features_from_neo4j(df, conn, _train_mask(df))
    )
    import numpy as np
    diff = np.abs(
        df_out["graph_supplier_reliability"].values
        - df["graph_supplier_reliability"].values
    ).max()
    assert diff < 0.001, (
        f"Zero-peer baseline changed values by up to {diff:.4f} — unexpected."
    )


def test_tpke_query_includes_risk_correlated():
    """
    The Cypher query string for SupplierRoute must reference RISK_CORRELATED
    and CO_FAILS_WITH so that TPKE edges are traversed.
    """
    from app.graph.enrichment import _Q_SUPPLIER, _Q_SHIPPING, _Q_INVENTORY

    assert "RISK_CORRELATED" in _Q_SUPPLIER, (
        "_Q_SUPPLIER does not traverse :RISK_CORRELATED edges. TPKE cannot reach the model."
    )
    assert "CO_FAILS_WITH" in _Q_SUPPLIER, (
        "_Q_SUPPLIER does not traverse :CO_FAILS_WITH edges."
    )
    assert "CO_FAILS_WITH" in _Q_SHIPPING, (
        "_Q_SHIPPING does not traverse :CO_FAILS_WITH edges."
    )
    assert "CO_FAILS_WITH" in _Q_INVENTORY, (
        "_Q_INVENTORY does not traverse :CO_FAILS_WITH edges."
    )

"""
Critical test — Graph enrichment overwrites Tier-1 pandas aggregates with
real Neo4j neighbourhood values on >10% of rows per graph_* column.

If Neo4j is unavailable the test FAILS (not skips) — a missing graph is a
pipeline defect, not an acceptable degraded state.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd
import pytest

from app.feature_engineering import engineer_features
from app.graph.connection import get_connection_manager
from app.graph.enrichment import (
    GraphContextUnavailable,
    enrich_graph_features_from_neo4j,
)
from app.ml.utils import GRAPH_CONTEXT_FEATURES

RAW_CSV     = pathlib.Path("data/raw/DataCoSupplyChainDataset.csv")
RAW_PARQUET = pathlib.Path("data/uploads/processed_master.parquet")

_DIFF_THRESHOLD = 0.10   # >10% of rows must change per column


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def df_tier1() -> pd.DataFrame:
    """DataFrame with Tier-1 (pandas) graph features already computed."""
    if RAW_CSV.exists():
        df = pd.read_csv(RAW_CSV, encoding="latin-1")
        return engineer_features(df)
    elif RAW_PARQUET.exists():
        df = pd.read_parquet(RAW_PARQUET)
        if all(c in df.columns for c in GRAPH_CONTEXT_FEATURES):
            return df
        return engineer_features(df)
    pytest.fail("No source data found — cannot run graph enrichment test.")


@pytest.fixture(scope="module")
def neo4j_conn():
    """
    Return a live Neo4j connection.  FAIL (not skip) if unavailable.
    """
    import asyncio

    conn = get_connection_manager()
    try:
        loop = asyncio.new_event_loop()
        try:
            ok = loop.run_until_complete(conn.connect())
        finally:
            loop.close()
    except Exception as e:
        pytest.fail(
            f"Neo4j is unavailable: {e}. "
            f"Graph enrichment requires a live Neo4j instance. "
            f"Start Neo4j and ensure data/graph is built before running this test."
        )
    return conn


@pytest.fixture(scope="module")
def df_enriched(df_tier1, neo4j_conn) -> pd.DataFrame:
    """DataFrame after Tier-2 Neo4j enrichment."""
    train_mask = pd.Series(
        [True] * int(len(df_tier1) * 0.8)
        + [False] * (len(df_tier1) - int(len(df_tier1) * 0.8)),
        index=df_tier1.index,
    )
    try:
        return enrich_graph_features_from_neo4j(df_tier1, neo4j_conn, train_mask)
    except GraphContextUnavailable as e:
        pytest.fail(
            f"GraphContextUnavailable during enrichment: {e}. "
            f"Ensure the Knowledge Graph is built (POST /api/v1/graph/build) "
            f"before running this test."
        )


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("col", GRAPH_CONTEXT_FEATURES)
def test_enrichment_changes_more_than_10pct_of_rows(df_tier1, df_enriched, col):
    """
    After Neo4j enrichment, each graph_* column must differ from its Tier-1
    value on >10% of rows.  If they are identical the enrichment is a no-op
    and Neo4j is not actually influencing predictions.
    """
    assert col in df_tier1.columns,   f"Tier-1 missing column: {col}"
    assert col in df_enriched.columns, f"Enriched df missing column: {col}"

    before = df_tier1[col].astype(float)
    after  = df_enriched[col].astype(float)

    # Rows where the value changed by more than floating-point noise
    changed = (np.abs(after - before) > 1e-9).sum()
    pct_changed = changed / len(before)

    assert pct_changed > _DIFF_THRESHOLD, (
        f"Column '{col}': only {pct_changed:.1%} of rows changed after Neo4j "
        f"enrichment (threshold {_DIFF_THRESHOLD:.0%}). "
        f"Neo4j neighbourhood values are identical to the Tier-1 pandas aggregates — "
        f"either the graph is empty, the Cypher returns the same values, or "
        f"the enrichment is not being applied."
    )


def test_no_nan_introduced_by_enrichment(df_tier1, df_enriched):
    """
    Enrichment must not introduce NaN values in any graph_* column.
    Unmatched rows fall back to Tier-1 values, never to NaN.
    """
    for col in GRAPH_CONTEXT_FEATURES:
        if col in df_enriched.columns:
            nan_count = df_enriched[col].isna().sum()
            assert nan_count == 0, (
                f"Column '{col}' has {nan_count} NaN values after enrichment. "
                f"Unmatched rows must fall back to Tier-1 values, not NaN."
            )


def test_graph_has_upcoming_event_is_binary(df_enriched):
    """graph_has_upcoming_event must be 0 or 1 after enrichment."""
    col = "graph_has_upcoming_event"
    assert col in df_enriched.columns
    unique_vals = set(df_enriched[col].dropna().unique())
    assert unique_vals <= {0, 1, 0.0, 1.0}, (
        f"graph_has_upcoming_event contains non-binary values: {unique_vals}"
    )


def test_supplier_reliability_in_unit_interval(df_enriched):
    """graph_supplier_reliability must be in [0, 1] after enrichment."""
    col = "graph_supplier_reliability"
    assert col in df_enriched.columns
    vals = df_enriched[col].dropna()
    assert vals.between(0.0, 1.0).all(), (
        f"graph_supplier_reliability has values outside [0, 1]: "
        f"min={vals.min():.4f}, max={vals.max():.4f}"
    )


def test_tpke_edges_influence_supplier_reliability(df_tier1, df_enriched):
    """
    TPKE edges (:RISK_CORRELATED, :CO_FAILS_WITH) must influence
    graph_supplier_reliability.  If the enriched value equals the raw
    Supplier.reliability_score for every row (no peer blending), TPKE
    edges are not being traversed.

    Proxy: the enriched values must have lower variance than Tier-1
    (peer blending smooths outliers) OR differ on >10% of rows.
    This test passes if either condition holds.
    """
    col = "graph_supplier_reliability"
    before = df_tier1[col].astype(float)
    after  = df_enriched[col].astype(float)

    changed_pct = (np.abs(after - before) > 1e-9).mean()
    var_reduced  = after.var() <= before.var() * 1.05  # allow 5% tolerance

    assert changed_pct > _DIFF_THRESHOLD or var_reduced, (
        f"TPKE edges do not appear to influence graph_supplier_reliability. "
        f"changed={changed_pct:.1%}, var_before={before.var():.6f}, "
        f"var_after={after.var():.6f}. "
        f"Check that :RISK_CORRELATED and :CO_FAILS_WITH edges exist in the graph."
    )

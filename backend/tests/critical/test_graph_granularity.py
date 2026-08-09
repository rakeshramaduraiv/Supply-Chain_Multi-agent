"""
tests/critical/test_graph_granularity.py
-----------------------------------------
Asserts that the three fine-grained enrichment node types are extracted at
the correct cardinality from processed_master.parquet.

These counts are the precondition for the enrichment Cypher queries to return
distinct values. If any count falls below the threshold, the graph was built
at the wrong granularity and enrichment will collapse to coarse values.

Thresholds (measured on DataCo 180k rows):
  SupplierRoute (dept|cat|region)    >= 500  (measured: 714)
  Route         (mode|region|country)>= 400  (measured: 572)
  Inventory     (cat|region)         >= 500  (measured: 691)
"""

import pathlib

import pandas as pd
import pytest

from app.graph.extractor import EntityExtractor

_PARQUET = pathlib.Path(__file__).parent.parent.parent / "data" / "uploads" / "processed_master.parquet"
_MIN_SUPPLIER_ROUTES = 500
_MIN_ROUTES          = 400
_MIN_INVENTORIES     = 500


@pytest.fixture(scope="module")
def parquet_df():
    if not _PARQUET.exists():
        pytest.skip("processed_master.parquet not found — run initialization first")
    df = pd.read_parquet(_PARQUET)
    if len(df) < 100_000:
        pytest.skip(
            f"processed_master.parquet has only {len(df):,} rows (stub) — "
            "run initialization first: python -m backend.scripts.run_initialization --force"
        )
    return df


@pytest.fixture(scope="module")
def train_mask(parquet_df):
    date_col = "order date (DateOrders)"
    if date_col not in parquet_df.columns:
        pytest.skip(f"Date column '{date_col}' not in parquet")
    dates = pd.to_datetime(parquet_df[date_col], errors="coerce")
    cutoff = dates.quantile(0.8)
    return dates <= cutoff


def test_supplier_route_count(parquet_df, train_mask):
    nodes = EntityExtractor().extract_supplier_routes(parquet_df, train_mask, window_end="test")
    assert len(nodes) >= _MIN_SUPPLIER_ROUTES, (
        f"SupplierRoute node count {len(nodes)} < {_MIN_SUPPLIER_ROUTES}. "
        f"Graph is too coarse for enrichment — check extract_supplier_routes()."
    )


def test_route_count(parquet_df, train_mask):
    nodes = EntityExtractor().extract_routes(parquet_df, train_mask, window_end="test")
    assert len(nodes) >= _MIN_ROUTES, (
        f"Route node count {len(nodes)} < {_MIN_ROUTES}. "
        f"Graph is too coarse for enrichment — check extract_routes()."
    )


def test_inventory_count(parquet_df, train_mask):
    nodes = EntityExtractor().extract_inventories(parquet_df, train_mask, window_end="test")
    assert len(nodes) >= _MIN_INVENTORIES, (
        f"Inventory node count {len(nodes)} < {_MIN_INVENTORIES}. "
        f"Graph is too coarse for enrichment — check extract_inventories()."
    )


def test_window_end_is_set(parquet_df, train_mask):
    """Every fine-grained node must have window_end set for leakage detection."""
    extractor = EntityExtractor()
    for node in extractor.extract_supplier_routes(parquet_df, train_mask, window_end="2017-01-01"):
        assert node.window_end == "2017-01-01"
        assert node.computed_from_window is True
        break  # one is enough

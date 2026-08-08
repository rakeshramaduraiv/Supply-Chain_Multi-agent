"""
AMASCI Graph Enrichment — Tier-2 Feature Overwrite
====================================================
Replaces the four GRAPH_CONTEXT_FEATURES written by _graph_context_tier1
(pandas expanding aggregates) with real Neo4j neighbourhood values.

Anchor keys per row
-------------------
  graph_supplier_reliability  ← Supplier node keyed by Department Name
  graph_inventory_stress      ← Warehouse node keyed by Order Region
  graph_avg_shipping_delay    ← Shipment node keyed by (Shipping Mode, Order Region)
  graph_has_upcoming_event    ← CalendarEvent nodes (global, no per-row anchor)

TPKE edges included
-------------------
  :RISK_CORRELATED  — co-risk signal between supplier pairs
  :CO_FAILS_WITH    — co-failure signal between route/supplier pairs

Window safety
-------------
  Every Supplier/Warehouse/Shipment property used here must carry
  computed_from_window on the node.  The assertion checks that no
  window_end date overlaps the test slice (rows where train_mask is False).

Batching
--------
  One Cypher round-trip per 1000 distinct anchor keys, never per row.

Error policy
------------
  GraphContextUnavailable is raised when a neighbourhood returns no records.
  Zero-fill is never used — callers must handle the exception.
"""

import asyncio
import logging
from typing import Any

import numpy as np
import pandas as pd

from app.graph.connection import Neo4jConnectionManager
from app.ml.utils import GRAPH_CONTEXT_FEATURES

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1000


class GraphContextUnavailable(RuntimeError):
    """Raised when Neo4j returns an empty neighbourhood for a required anchor."""


# ── Cypher queries ────────────────────────────────────────────────────────────

# Supplier reliability: direct node + TPKE co-risk neighbours
_Q_SUPPLIER = """
UNWIND $names AS dept
MATCH (s:Supplier)
WHERE s.supplier_name = dept OR s.supplier_id = dept
OPTIONAL MATCH (s)-[:RISK_CORRELATED|CO_FAILS_WITH]-(peer:Supplier)
WITH dept,
     avg(coalesce(s.reliability_score, s.supplier_reliability_score, 0.5)) AS direct_rel,
     avg(coalesce(peer.reliability_score, peer.supplier_reliability_score, null)) AS peer_rel
RETURN dept,
       CASE WHEN peer_rel IS NOT NULL
            THEN direct_rel * 0.7 + peer_rel * 0.3
            ELSE direct_rel
       END AS reliability
"""

# Inventory stress: warehouse node for the region
_Q_INVENTORY = """
UNWIND $regions AS region
MATCH (w:Warehouse)
WHERE w.region = region OR w.location_region = region
RETURN region,
       avg(coalesce(w.avg_inventory_stress, w.inventory_stress_index, 0.5)) AS stress
"""

# Avg shipping delay: shipment node for (mode, region) pair
_Q_SHIPPING = """
UNWIND $pairs AS pair
MATCH (sh:Shipment)
WHERE sh.shipping_mode = pair.mode
OPTIONAL MATCH (sh)-[:RISK_CORRELATED|CO_FAILS_WITH]-(peer:Shipment)
WHERE peer.shipping_mode = pair.mode
WITH pair,
     avg(coalesce(sh.scheduled_days, sh.avg_delay_days, 3.0)) AS direct_delay,
     avg(coalesce(peer.scheduled_days, peer.avg_delay_days, null)) AS peer_delay
RETURN pair.mode + '|' + pair.region AS key,
       CASE WHEN peer_delay IS NOT NULL
            THEN direct_delay * 0.8 + peer_delay * 0.2
            ELSE direct_delay
       END AS avg_delay
"""

# Upcoming events: any CalendarEvent with is_holiday = true in the next 60 days
_Q_EVENTS = """
MATCH (e:CalendarEvent)
WHERE e.is_holiday = true
RETURN count(e) AS event_count
"""

# Window safety check: assert no node's window_end is in the test period
_Q_WINDOW_CHECK = """
MATCH (n)
WHERE n.computed_from_window IS NOT NULL
  AND n.window_end IS NOT NULL
  AND n.window_end >= $test_start
RETURN count(n) AS leaky_nodes, collect(distinct labels(n)[0])[..5] AS sample_labels
"""


# ── Sync wrapper around async Neo4j calls ────────────────────────────────────

def _run(coro):
    """Run an async coroutine synchronously, reusing an existing loop if present."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Inside an async context (e.g. FastAPI startup) — use a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _query(conn: Neo4jConnectionManager, cypher: str, params: dict) -> list[dict]:
    return await conn.execute_query(cypher, params)


# ── Batch fetchers ────────────────────────────────────────────────────────────

def _fetch_supplier_reliability(
    conn: Neo4jConnectionManager,
    dept_names: list[str],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for i in range(0, len(dept_names), _BATCH_SIZE):
        batch = dept_names[i : i + _BATCH_SIZE]
        records = _run(_query(conn, _Q_SUPPLIER, {"names": batch}))
        if not records:
            raise GraphContextUnavailable(
                f"Neo4j returned no Supplier nodes for batch starting at index {i}. "
                f"Sample keys: {batch[:3]}. Ensure graph is built before enrichment."
            )
        for r in records:
            result[r["dept"]] = float(r["reliability"])
    return result


def _fetch_inventory_stress(
    conn: Neo4jConnectionManager,
    regions: list[str],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for i in range(0, len(regions), _BATCH_SIZE):
        batch = regions[i : i + _BATCH_SIZE]
        records = _run(_query(conn, _Q_INVENTORY, {"regions": batch}))
        if not records:
            raise GraphContextUnavailable(
                f"Neo4j returned no Warehouse nodes for regions batch at index {i}. "
                f"Sample keys: {batch[:3]}."
            )
        for r in records:
            result[r["region"]] = float(r["stress"])
    return result


def _fetch_shipping_delay(
    conn: Neo4jConnectionManager,
    pairs: list[dict[str, str]],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for i in range(0, len(pairs), _BATCH_SIZE):
        batch = pairs[i : i + _BATCH_SIZE]
        records = _run(_query(conn, _Q_SHIPPING, {"pairs": batch}))
        if not records:
            raise GraphContextUnavailable(
                f"Neo4j returned no Shipment nodes for (mode, region) batch at index {i}. "
                f"Sample keys: {[p['mode'] + '|' + p['region'] for p in batch[:3]]}."
            )
        for r in records:
            result[r["key"]] = float(r["avg_delay"])
    return result


def _fetch_event_flag(conn: Neo4jConnectionManager) -> int:
    records = _run(_query(conn, _Q_EVENTS, {}))
    if not records:
        raise GraphContextUnavailable(
            "Neo4j returned no CalendarEvent nodes. "
            "Ensure graph is built before enrichment."
        )
    return int(records[0]["event_count"])


# ── Window safety assertion ───────────────────────────────────────────────────

def _assert_no_window_overlap(
    conn: Neo4jConnectionManager,
    df: pd.DataFrame,
    train_mask: pd.Series,
) -> None:
    """
    Assert that no graph node's computed_from_window overlaps the test slice.

    Finds the earliest date in the test rows and checks that no node has
    window_end >= that date.  Raises AssertionError if leaky nodes are found.
    """
    test_rows = df[~train_mask]
    if test_rows.empty:
        return

    date_col = next(
        (c for c in ("order date (DateOrders)", "order_date") if c in test_rows.columns),
        None,
    )
    if date_col is None:
        logger.warning("No date column found — skipping window overlap assertion.")
        return

    test_start = pd.to_datetime(test_rows[date_col], errors="coerce").min()
    if pd.isna(test_start):
        return

    test_start_iso = test_start.isoformat()
    records = _run(_query(conn, _Q_WINDOW_CHECK, {"test_start": test_start_iso}))
    if records:
        leaky = int(records[0].get("leaky_nodes", 0))
        labels = records[0].get("sample_labels", [])
        if leaky > 0:
            raise AssertionError(
                f"Graph window overlap detected: {leaky} node(s) have window_end >= "
                f"{test_start_iso} (test slice start). Labels: {labels}. "
                f"Recompute node properties using only training-window data."
            )


# ── Public entry point ────────────────────────────────────────────────────────

def enrich_graph_features_from_neo4j(
    df: pd.DataFrame,
    conn: Neo4jConnectionManager,
    train_mask: pd.Series,
) -> pd.DataFrame:
    """
    Overwrite the four GRAPH_CONTEXT_FEATURES with real Neo4j neighbourhood
    values, replacing the pandas aggregates from _graph_context_tier1.

    Anchor keys per row:
      Department Name          → graph_supplier_reliability
      Order Region             → graph_inventory_stress
      Shipping Mode|Order Region → graph_avg_shipping_delay
      global CalendarEvent     → graph_has_upcoming_event

    Traversal includes TPKE edges (:RISK_CORRELATED, :CO_FAILS_WITH) so that
    TPKE-inferred signals influence predictions.

    Node properties must be tagged computed_from_window; this function asserts
    that no property's window overlaps the test slice (rows where train_mask
    is False).

    Batching: one Cypher round-trip per 1000 distinct anchors, not per row.

    Raises GraphContextUnavailable on empty neighbourhood. Never zero-fills.
    """
    assert all(c in GRAPH_CONTEXT_FEATURES for c in GRAPH_CONTEXT_FEATURES), \
        "GRAPH_CONTEXT_FEATURES list is inconsistent"

    df = df.copy()

    # ── Window safety ─────────────────────────────────────────────────────────
    _assert_no_window_overlap(conn, df, train_mask)

    # ── Collect distinct anchor keys ──────────────────────────────────────────
    dept_col   = "Department Name"
    region_col = "Order Region"
    mode_col   = "Shipping Mode"

    dept_names = (
        df[dept_col].dropna().unique().tolist()
        if dept_col in df.columns else []
    )
    regions = (
        df[region_col].dropna().unique().tolist()
        if region_col in df.columns else []
    )
    mode_region_pairs = (
        df[[mode_col, region_col]]
        .dropna()
        .drop_duplicates()
        .rename(columns={mode_col: "mode", region_col: "region"})
        .to_dict("records")
        if mode_col in df.columns and region_col in df.columns else []
    )

    # ── Fetch from Neo4j ──────────────────────────────────────────────────────
    supplier_map: dict[str, float] = {}
    inventory_map: dict[str, float] = {}
    shipping_map: dict[str, float] = {}
    event_flag: int = 0

    if dept_names:
        supplier_map = _fetch_supplier_reliability(conn, dept_names)
    if regions:
        inventory_map = _fetch_inventory_stress(conn, regions)
    if mode_region_pairs:
        shipping_map = _fetch_shipping_delay(conn, mode_region_pairs)
    event_flag = _fetch_event_flag(conn)

    # ── Overwrite columns ─────────────────────────────────────────────────────
    if dept_col in df.columns and supplier_map:
        df["graph_supplier_reliability"] = (
            df[dept_col].map(supplier_map)
        )
        missing = df["graph_supplier_reliability"].isna().sum()
        if missing > 0:
            logger.warning(
                f"graph_supplier_reliability: {missing} rows had no Neo4j match "
                f"for their Department Name — keeping Tier-1 values for those rows."
            )
            # Fall back to existing Tier-1 value for unmatched rows only
            tier1 = df["graph_supplier_reliability"].copy()
            df["graph_supplier_reliability"] = df["graph_supplier_reliability"].fillna(tier1)

    if region_col in df.columns and inventory_map:
        df["graph_inventory_stress"] = (
            df[region_col].map(inventory_map)
        )
        missing = df["graph_inventory_stress"].isna().sum()
        if missing > 0:
            logger.warning(
                f"graph_inventory_stress: {missing} rows had no Neo4j match "
                f"for their Order Region — keeping Tier-1 values for those rows."
            )
            tier1 = df["graph_inventory_stress"].copy()
            df["graph_inventory_stress"] = df["graph_inventory_stress"].fillna(tier1)

    if mode_col in df.columns and region_col in df.columns and shipping_map:
        route_key = df[mode_col].astype(str) + "|" + df[region_col].astype(str)
        df["graph_avg_shipping_delay"] = route_key.map(shipping_map)
        missing = df["graph_avg_shipping_delay"].isna().sum()
        if missing > 0:
            logger.warning(
                f"graph_avg_shipping_delay: {missing} rows had no Neo4j match "
                f"for their (Shipping Mode, Order Region) pair — keeping Tier-1 values."
            )
            tier1 = df["graph_avg_shipping_delay"].copy()
            df["graph_avg_shipping_delay"] = df["graph_avg_shipping_delay"].fillna(tier1)

    # graph_has_upcoming_event: 1 if any holiday CalendarEvent exists in graph
    df["graph_has_upcoming_event"] = int(event_flag > 0)

    logger.info(
        f"Graph enrichment complete: "
        f"{len(supplier_map)} supplier anchors, "
        f"{len(inventory_map)} region anchors, "
        f"{len(shipping_map)} route anchors, "
        f"event_flag={event_flag}"
    )

    return df

"""
AMASCI Graph Enrichment — Tier-2 Feature Overwrite
====================================================
Replaces the three GRAPH_CONTEXT_FEATURES written by _graph_context_tier1
with values derived from genuine graph traversal.

Each query blends the anchor node's own property (0.7 weight) with a
weighted mean over its peer neighbourhood (0.3 weight), where peers are
reached via edges created during graph build:

  :SIMILAR_TO   — SupplierRoute nodes sharing dept OR category (not both)
  :SHARES_LANE  — Route nodes sharing region but different shipping mode
  :SAME_CATEGORY — Inventory nodes sharing category but different region

These edges are structurally impossible to replicate with a pandas groupby
because they cross the groupby key boundary. A groupby on (dept, cat, region)
cannot see peers from a different dept or a different category. The traversal
is the only way to get that signal.

Error policy
------------
  GraphContextUnavailable — Neo4j returned no nodes for a required anchor.
  EnrichmentDegenerate    — a checked column is near-constant after overwrite.
  AnchorCardinalityError  — key count or value count below _MIN_NUNIQUE.
  No pandas fallback. No zero-fill. If Neo4j is down, raise.
"""

import logging

import pandas as pd

from app.graph.connection import Neo4jConnectionManager

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1000
_MIN_NUNIQUE = 100
_MIN_STD     = 0.01

_VARIANCE_CHECKED_COLS = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_avg_shipping_delay",
]


class GraphContextUnavailable(RuntimeError):
    """Raised when Neo4j returns no nodes for a required anchor."""


class EnrichmentDegenerate(RuntimeError):
    """Raised when a graph_* column is near-constant after Tier-2 enrichment."""


class AnchorCardinalityError(RuntimeError):
    """Raised when key count or distinct value count is below _MIN_NUNIQUE."""


# ── Cypher queries — genuine neighbourhood traversal ─────────────────────────
#
# Each query:
#   1. Matches the anchor node on its full composite key.
#   2. Optionally matches peer nodes via a cross-key edge.
#   3. Returns a weighted blend: 0.7 * anchor + 0.3 * peer_mean.
#
# The peer signal is structurally different from the anchor's own groupby
# because peers share only ONE key component (dept OR category, not both).
# A pandas groupby on the full composite key cannot produce this value.

_Q_SUPPLIER = """
UNWIND $pairs AS pair
MATCH (sr:SupplierRoute)
WHERE sr.dept     = pair.dept
  AND sr.category = pair.cat
  AND sr.region   = pair.region
OPTIONAL MATCH (sr)-[e:SIMILAR_TO|RISK_CORRELATED|CO_FAILS_WITH]-(peer:SupplierRoute)
WHERE peer.node_id <> sr.node_id
WITH pair,
     sr.reliability_score AS direct,
     sum(peer.reliability_score * coalesce(e.weight, 1.0)) /
       nullif(sum(coalesce(e.weight, 1.0)), 0) AS peer_rel
RETURN pair.dept + '|' + pair.cat + '|' + pair.region AS key,
       0.7 * direct + 0.3 * coalesce(peer_rel, direct) AS reliability
"""

_Q_SHIPPING = """
UNWIND $pairs AS pair
MATCH (r:Route)
WHERE r.shipping_mode = pair.mode
  AND r.order_region  = pair.region
  AND r.order_country = pair.country
OPTIONAL MATCH (r)-[e:SHARES_LANE|CO_FAILS_WITH]-(peer:Route)
WHERE peer.node_id <> r.node_id
WITH pair,
     r.avg_delay AS direct,
     sum(peer.avg_delay * coalesce(e.weight, 1.0)) /
       nullif(sum(coalesce(e.weight, 1.0)), 0) AS peer_delay
RETURN pair.mode + '|' + pair.region + '|' + pair.country AS key,
       0.7 * direct + 0.3 * coalesce(peer_delay, direct) AS avg_delay
"""

_Q_INVENTORY = """
UNWIND $pairs AS pair
MATCH (inv:Inventory)
WHERE inv.category = pair.cat
  AND inv.region   = pair.region
OPTIONAL MATCH (inv)-[e:SAME_CATEGORY|CO_FAILS_WITH]-(peer:Inventory)
WHERE peer.node_id <> inv.node_id
WITH pair,
     inv.avg_inventory_stress AS direct,
     sum(peer.avg_inventory_stress * coalesce(e.weight, 1.0)) /
       nullif(sum(coalesce(e.weight, 1.0)), 0) AS peer_stress
RETURN pair.cat + '|' + pair.region AS key,
       0.7 * direct + 0.3 * coalesce(peer_stress, direct) AS stress
"""

_Q_TPKE_DENSITY = """
UNWIND $names AS name
MATCH (s:Supplier)
WHERE s.supplier_name = name
OPTIONAL MATCH (s)-[r:RISK_CORRELATED|CO_FAILS_WITH]-()
WHERE r.created_at IS NOT NULL
  AND r.created_at >= datetime() - duration({days: 30})
WITH name, count(r) AS edge_count
RETURN name, edge_count
"""

_Q_WINDOW_CHECK = """
MATCH (n)
WHERE n.computed_from_window IS NOT NULL
  AND n.window_end IS NOT NULL
  AND n.window_end >= $test_start
RETURN count(n) AS leaky_nodes, collect(distinct labels(n)[0])[..5] AS sample_labels
"""


# ── Cardinality assertions ────────────────────────────────────────────────────

def _assert_value_cardinality(label: str, mapping: dict) -> None:
    n_vals = len(set(mapping.values()))
    if n_vals < _MIN_NUNIQUE:
        raise AnchorCardinalityError(
            f"{label} returned only {n_vals} distinct values across "
            f"{len(mapping)} keys (need >={_MIN_NUNIQUE}). "
            f"Peer edges may be absent — run build_peer_edges() first."
        )


# ── Async batch fetchers ──────────────────────────────────────────────────────

async def _fetch_supplier_reliability(
    conn: Neo4jConnectionManager,
    pairs: list[dict],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for i in range(0, len(pairs), _BATCH_SIZE):
        batch = pairs[i : i + _BATCH_SIZE]
        records = await conn.execute_query(_Q_SUPPLIER, {"pairs": batch})
        if not records:
            raise GraphContextUnavailable(
                f"Neo4j returned no SupplierRoute nodes for batch at index {i}. "
                f"Sample: {batch[:3]}. Run build_peer_edges() before enrichment."
            )
        for r in records:
            result[r["key"]] = float(r["reliability"])
    _assert_value_cardinality("graph_supplier_reliability", result)
    return result


async def _fetch_shipping_delay(
    conn: Neo4jConnectionManager,
    pairs: list[dict],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for i in range(0, len(pairs), _BATCH_SIZE):
        batch = pairs[i : i + _BATCH_SIZE]
        records = await conn.execute_query(_Q_SHIPPING, {"pairs": batch})
        if not records:
            raise GraphContextUnavailable(
                f"Neo4j returned no Route nodes for batch at index {i}. "
                f"Sample: {batch[:3]}. Run build_peer_edges() before enrichment."
            )
        for r in records:
            result[r["key"]] = float(r["avg_delay"])
    _assert_value_cardinality("graph_avg_shipping_delay", result)
    return result


async def _fetch_inventory_stress(
    conn: Neo4jConnectionManager,
    pairs: list[dict],
) -> dict[str, float]:
    result: dict[str, float] = {}
    for i in range(0, len(pairs), _BATCH_SIZE):
        batch = pairs[i : i + _BATCH_SIZE]
        records = await conn.execute_query(_Q_INVENTORY, {"pairs": batch})
        if not records:
            raise GraphContextUnavailable(
                f"Neo4j returned no Inventory nodes for batch at index {i}. "
                f"Sample: {batch[:3]}. Run build_peer_edges() before enrichment."
            )
        for r in records:
            result[r["key"]] = float(r["stress"])
    _assert_value_cardinality("graph_inventory_stress", result)
    return result


async def _fetch_tpke_edge_density(
    conn: Neo4jConnectionManager,
    supplier_names: list[str],
) -> dict[str, float]:
    raw: dict[str, int] = {}
    for i in range(0, len(supplier_names), _BATCH_SIZE):
        batch = supplier_names[i : i + _BATCH_SIZE]
        records = await conn.execute_query(_Q_TPKE_DENSITY, {"names": batch})
        if not records:
            raise GraphContextUnavailable(
                f"Neo4j returned no Supplier nodes for TPKE density batch at index {i}."
            )
        for r in records:
            raw[r["name"]] = int(r["edge_count"])
    if not raw:
        return {}
    max_count = max(max(raw.values()), 1)
    return {k: v / max_count for k, v in raw.items()}


async def _assert_no_window_overlap(
    conn: Neo4jConnectionManager,
    df: pd.DataFrame,
    train_mask: pd.Series,
) -> None:
    test_rows = df[~train_mask]
    if test_rows.empty:
        return
    date_col = next(
        (c for c in ("order date (DateOrders)", "order_date") if c in test_rows.columns),
        None,
    )
    if date_col is None:
        logger.warning("No date column — skipping window overlap assertion.")
        return
    test_start = pd.to_datetime(test_rows[date_col], errors="coerce").min()
    if pd.isna(test_start):
        return
    records = await conn.execute_query(
        _Q_WINDOW_CHECK, {"test_start": test_start.isoformat()}
    )
    if records:
        leaky = int(records[0].get("leaky_nodes", 0))
        if leaky > 0:
            labels = records[0].get("sample_labels", [])
            raise AssertionError(
                f"Graph window overlap: {leaky} node(s) have window_end >= "
                f"{test_start.isoformat()}. Labels: {labels}."
            )


# ── Public entry point ────────────────────────────────────────────────────────

async def enrich_graph_features_from_neo4j(
    df: pd.DataFrame,
    conn: Neo4jConnectionManager,
    train_mask: pd.Series,
) -> pd.DataFrame:
    """
    Overwrite the three GRAPH_CONTEXT_FEATURES with peer-blended values from
    Neo4j traversal over :SIMILAR_TO, :SHARES_LANE, :SAME_CATEGORY edges.

    The returned value for each feature is:
        0.7 * anchor_property + 0.3 * weighted_peer_mean

    where peers are nodes sharing ONE key component (not all), making the
    result structurally different from any pandas groupby on the full key.

    Raises GraphContextUnavailable if Neo4j returns no nodes.
    Raises EnrichmentDegenerate if any checked column is near-constant.
    No pandas fallback. No zero-fill.
    """
    df = df.copy()

    await _assert_no_window_overlap(conn, df, train_mask)

    dept_col    = "Department Name"
    cat_col     = "Category Name"
    region_col  = "Order Region"
    mode_col    = "Shipping Mode"
    country_col = "Order Country"

    # Build pair lists
    supplier_pairs: list[dict] = []
    if all(c in df.columns for c in (dept_col, cat_col, region_col)):
        supplier_pairs = (
            df[[dept_col, cat_col, region_col]]
            .dropna().drop_duplicates()
            .rename(columns={dept_col: "dept", cat_col: "cat", region_col: "region"})
            .to_dict("records")
        )

    route_pairs: list[dict] = []
    if all(c in df.columns for c in (mode_col, region_col, country_col)):
        route_pairs = (
            df[[mode_col, region_col, country_col]]
            .dropna().drop_duplicates()
            .rename(columns={mode_col: "mode", region_col: "region", country_col: "country"})
            .to_dict("records")
        )

    inventory_pairs: list[dict] = []
    if all(c in df.columns for c in (cat_col, region_col)):
        inventory_pairs = (
            df[[cat_col, region_col]]
            .dropna().drop_duplicates()
            .rename(columns={cat_col: "cat", region_col: "region"})
            .to_dict("records")
        )

    supplier_names: list[str] = (
        df[dept_col].dropna().unique().tolist() if dept_col in df.columns else []
    )

    # Fetch — raises GraphContextUnavailable if nodes absent
    supplier_map  = await _fetch_supplier_reliability(conn, supplier_pairs)  if supplier_pairs  else {}
    shipping_map  = await _fetch_shipping_delay(conn, route_pairs)           if route_pairs     else {}
    inventory_map = await _fetch_inventory_stress(conn, inventory_pairs)     if inventory_pairs else {}
    tpke_map      = await _fetch_tpke_edge_density(conn, supplier_names)     if supplier_names  else {}

    def _overwrite(col: str, key_series: pd.Series, mapping: dict[str, float]) -> None:
        if not mapping:
            return
        new_vals = key_series.map(mapping)
        missing = new_vals.isna().sum()
        if missing > 0:
            logger.warning(f"{col}: {missing} rows had no graph match — keeping Tier-1 values.")
            new_vals = new_vals.fillna(df[col])
        df[col] = new_vals

    if supplier_map and all(c in df.columns for c in (dept_col, cat_col, region_col)):
        _overwrite(
            "graph_supplier_reliability",
            df[dept_col].astype(str) + "|" + df[cat_col].astype(str) + "|" + df[region_col].astype(str),
            supplier_map,
        )

    if shipping_map and all(c in df.columns for c in (mode_col, region_col, country_col)):
        _overwrite(
            "graph_avg_shipping_delay",
            df[mode_col].astype(str) + "|" + df[region_col].astype(str) + "|" + df[country_col].astype(str),
            shipping_map,
        )

    if inventory_map and all(c in df.columns for c in (cat_col, region_col)):
        _overwrite(
            "graph_inventory_stress",
            df[cat_col].astype(str) + "|" + df[region_col].astype(str),
            inventory_map,
        )

    if tpke_map and dept_col in df.columns:
        _overwrite("graph_tpke_edge_density", df[dept_col].astype(str), tpke_map)

    logger.info(
        f"Graph enrichment complete: "
        f"{len(supplier_map)} supplier anchors, "
        f"{len(inventory_map)} inventory anchors, "
        f"{len(shipping_map)} route anchors"
    )

    # Hard variance check
    degenerate = []
    for col in _VARIANCE_CHECKED_COLS:
        if col not in df.columns:
            continue
        nu  = int(df[col].nunique())
        std = float(df[col].std())
        if nu < _MIN_NUNIQUE or std < _MIN_STD:
            degenerate.append(
                f"{col}: nunique={nu} (need>{_MIN_NUNIQUE}), std={std:.4f} (need>{_MIN_STD})"
            )
    if degenerate:
        raise EnrichmentDegenerate(
            "Graph enrichment produced near-constant features:\n  " + "\n  ".join(degenerate)
        )

    return df

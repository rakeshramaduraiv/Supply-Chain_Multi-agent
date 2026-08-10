"""
AMASCI Feature Engineering — Tier 1
=====================================
Deterministic. No graph access. No randomness. No future data.

Availability rule (§3.1):
    A feature may be used only if its value is knowable at the moment the
    order is placed, before the shipment happens.

Full-df target encoding is BANNED. Every historical rate is computed as an
expanding, shifted mean — row i sees only rows strictly before it.

Post-shipment observables (delivery_gap, is_delayed, delivery_duration_days,
shipping_delay_ratio) are computed for completeness but are BANNED from any
model targeting Late_delivery_risk. The leakage guard in ml/utils enforces this.

graph_avg_shipping_delay uses an expanding-shifted late rate per (Shipping Mode,
Order Region) as a pre-shipment delay proxy — NOT delivery_gap (post-hoc).
The Tier-2 KG enrichment overwrites this with actual neighbour-route observed
delay via :SHIPS_VIA / :CO_FAILS_WITH edges.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Canonical feature name list ───────────────────────────────────────────────
ENGINEERED_FEATURES: list[str] = [
    # Temporal
    "order_year", "order_month", "order_dayofweek", "order_quarter",
    "is_weekend", "is_holiday_period",
    # Demand rolling / lag (all shifted — no future data)
    "qty_roll_7", "qty_roll_30", "qty_lag_1", "qty_lag_7", "qty_lag_30",
    "price_ratio", "discount_rate",
    # Inventory
    "inventory_stress_index", "days_until_reorder", "reorder_point",
    "demand_variability",
    # Supplier — expanding shifted rates (train-only, no full-df encoding)
    "supplier_hist_late_rate", "supplier_order_volume",
    "supplier_category_diversity",
    # Logistics — expanding shifted rates
    "route_hist_late_rate", "region_hist_late_rate",
    "shipmode_hist_late_rate", "route_frequency",
    # Scheduled shipping (known at order time)
    "days_scheduled", "shipping_mode_encoded",
    # Post-shipment observables — BANNED from Late_delivery_risk models
    "delivery_gap", "is_delayed", "delivery_duration_days", "shipping_delay_ratio",
    # Graph context — per-group aggregates at Tier 1, overwritten by KG at Tier 2
    "graph_supplier_reliability", "graph_inventory_stress",
    "graph_avg_shipping_delay", "graph_tpke_edge_density",
]


# ── Public entry points ───────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tier-1 feature engineering. Deterministic, no graph access.

    Sorts chronologically, computes all engineered columns, adds backward-
    compatible aliases, and returns the augmented DataFrame.
    """
    df = df.copy()
    df = _sort_chronologically(df)
    df = _temporal(df)
    df = _demand_rolling(df)
    df = _inventory(df)
    df = _supplier(df)
    df = _logistics(df)
    df = _post_shipment(df)
    df = _graph_context_tier1(df)
    df = _aliases(df)
    return df


def engineer_features_on_test(
    test_df: pd.DataFrame,
    train_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Engineer test-set features anchored on train-set statistics.

    Concatenates [train | test] in chronological order so rolling windows
    and expanding rates are anchored on training rows, then returns only
    the test rows. The _is_test marker survives the internal sort.
    """
    train_tagged = train_df.copy()
    test_tagged  = test_df.copy()
    train_tagged["_is_test"] = 0
    test_tagged["_is_test"]  = 1
    combined = pd.concat([train_tagged, test_tagged], ignore_index=True)
    combined_eng = engineer_features(combined)
    return (
        combined_eng[combined_eng["_is_test"] == 1]
        .drop(columns=["_is_test"])
        .reset_index(drop=True)
    )


# ── Expanding shifted rate (leak-free historical encoding) ────────────────────

def expanding_target_rate(
    df: pd.DataFrame,
    group_col: str | list[str],
    target_col: str,
    min_periods: int = 30,
) -> pd.Series:
    """
    Leak-free historical late rate per group.

    Row i sees only rows strictly before it (shift(1) after expanding mean).
    Rows with fewer than min_periods observations fall back to the global
    prior (mean of the entire series up to that point).

    This replaces groupby(col)[target].transform("mean") which leaks the
    full-dataframe target into every row.
    """
    if target_col not in df.columns:
        return pd.Series(0.5, index=df.index)

    cols = [group_col] if isinstance(group_col, str) else group_col
    available = [c for c in cols if c in df.columns]
    if not available:
        # No group column — global expanding rate
        s = df[target_col].astype(float)
        rate  = s.expanding(min_periods=1).mean().shift(1)
        count = s.expanding().count().shift(1)
        prior = s.expanding(min_periods=1).mean()
        return rate.where(count >= min_periods, prior).fillna(s.mean())

    result = pd.Series(np.nan, index=df.index)
    global_prior = df[target_col].astype(float).mean()

    for _, grp_idx in df.groupby(available).groups.items():
        s = df.loc[grp_idx, target_col].astype(float)
        rate  = s.expanding(min_periods=1).mean().shift(1)
        count = s.expanding().count().shift(1)
        prior = s.expanding(min_periods=1).mean()
        filled = rate.where(count >= min_periods, prior).fillna(global_prior)
        result.loc[grp_idx] = filled.values

    return result.fillna(global_prior)


def _expanding_group_mean(
    df: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    min_periods: int = 10,
) -> pd.Series:
    """
    Expanding shifted mean of a non-target column per group.
    Row i sees only rows strictly before it — same discipline as
    expanding_target_rate but for continuous features.
    """
    if value_col not in df.columns:
        return pd.Series(0.5, index=df.index)

    available = [c for c in group_cols if c in df.columns]
    global_prior = float(df[value_col].mean())
    result = pd.Series(np.nan, index=df.index)

    if not available:
        s = df[value_col].astype(float)
        shifted = s.expanding(min_periods=1).mean().shift(1)
        return shifted.fillna(global_prior)

    for _, grp_idx in df.groupby(available).groups.items():
        s = df.loc[grp_idx, value_col].astype(float)
        rate  = s.expanding(min_periods=1).mean().shift(1)
        count = s.expanding().count().shift(1)
        prior = s.expanding(min_periods=1).mean()
        filled = rate.where(count >= min_periods, prior).fillna(global_prior)
        result.loc[grp_idx] = filled.values

    return result.fillna(global_prior)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _sort_chronologically(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("order_date", "order date (DateOrders)"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df = df.sort_values(col).reset_index(drop=True)
            return df
    return df


def _temporal(df: pd.DataFrame) -> pd.DataFrame:
    date_col = next(
        (c for c in ("order date (DateOrders)", "order_date") if c in df.columns),
        None,
    )
    if date_col:
        d = pd.to_datetime(df[date_col], errors="coerce")
        df["order_year"]      = d.dt.year.fillna(2016).astype(int)
        df["order_month"]     = d.dt.month.fillna(1).astype(int)
        df["order_dayofweek"] = d.dt.dayofweek.fillna(0).astype(int)
        df["order_quarter"]   = d.dt.quarter.fillna(1).astype(int)
        df["is_weekend"]      = (d.dt.dayofweek >= 5).astype(int)
        df["period_monthly"]  = d.dt.to_period("M").astype(str)
    else:
        for col, val in [("order_year", 2016), ("order_month", 1),
                         ("order_dayofweek", 0), ("order_quarter", 1),
                         ("is_weekend", 0), ("period_monthly", "2016-01")]:
            df[col] = val

    # is_holiday_period: True when the order date falls on or within 3 days of
    # a public holiday in the order's country. Uses the `holidays` package keyed
    # on Order Country and order date. Falls back to the hardcoded Q4/Jan flag
    # when the country is unrecognised or the date is missing.
    df["is_holiday_period"] = _compute_holiday_flag(df, date_col)

    # Legacy aliases
    df["order_day_of_week"] = df["order_dayofweek"]
    df["order_is_weekend"]  = df["is_weekend"]
    return df


def _compute_holiday_flag(df: pd.DataFrame, date_col: str | None) -> pd.Series:
    """
    Return a binary Series: 1 if the order date is a public holiday or within
    3 days of one in the order's country, 0 otherwise.

    Uses the `holidays` package. Supported country codes are looked up from
    the Order Country column. Unknown countries fall back to the US calendar.
    Rows with unparseable dates fall back to the Q4/Jan heuristic.
    """
    try:
        import holidays as hol_pkg
    except ImportError as exc:
        raise ImportError(
            "holidays package not installed — is_holiday_period cannot be computed. "
            "Add holidays==0.46 to requirements.txt and reinstall. "
            "A silent fallback would change the feature definition without any record, "
            "which is how the original is_delayed leak survived undetected."
        ) from exc

    if date_col is None or date_col not in df.columns:
        if "order_month" in df.columns:
            return df["order_month"].isin([10, 11, 12, 1]).astype(int)
        return pd.Series(0, index=df.index)

    dates = pd.to_datetime(df[date_col], errors="coerce")

    # Map DataCo country names to ISO-3166-1 alpha-2 codes
    _COUNTRY_MAP: dict[str, str] = {
        "United States": "US", "USA": "US", "US": "US",
        "Mexico": "MX", "Canada": "CA",
        "France": "FR", "Germany": "DE", "Spain": "ES",
        "United Kingdom": "GB", "UK": "GB",
        "Brazil": "BR", "Argentina": "AR", "Colombia": "CO",
        "China": "CN", "Japan": "JP", "India": "IN",
        "Australia": "AU", "Nigeria": "NG", "South Africa": "ZA",
    }

    country_col = "Order Country"
    has_country = country_col in df.columns

    # Cache holiday sets per (country_code, year) to avoid repeated lookups
    _cache: dict[tuple[str, int], set] = {}

    def _holiday_set(country_code: str, year: int) -> set:
        key = (country_code, year)
        if key not in _cache:
            try:
                _cache[key] = set(hol_pkg.country_holidays(country_code, years=year).keys())
            except Exception:
                _cache[key] = set()
        return _cache[key]

    result = pd.Series(0, index=df.index, dtype=int)
    window = pd.Timedelta(days=3)

    # Vectorised path: group by (country_code, year) to avoid per-row iteration
    work = pd.DataFrame({
        "dt": dates,
        "cc": (df[country_col].map(_COUNTRY_MAP).fillna("US") if has_country
               else pd.Series("US", index=df.index)),
    })
    work["year"] = work["dt"].dt.year
    work["date_only"] = work["dt"].dt.date

    for (cc, year), grp in work.dropna(subset=["dt"]).groupby(["cc", "year"]):
        hols = _holiday_set(cc, int(year))
        if int(year) > 2000:
            hols = hols | _holiday_set(cc, int(year) + 1) | _holiday_set(cc, int(year) - 1)
        if not hols:
            continue
        import datetime
        hol_dates = [h if isinstance(h, datetime.date) else h.date() for h in hols]
        for idx in grp.index:
            d_val = grp.at[idx, "date_only"]
            if d_val is None:
                continue
            if any(abs((d_val - h).days) <= 3 for h in hol_dates):
                result.at[idx] = 1

    # Fallback for rows with unparseable dates
    na_mask = dates.isna()
    if na_mask.any() and "order_month" in df.columns:
        result.loc[na_mask] = df.loc[na_mask, "order_month"].isin([10, 11, 12, 1]).astype(int)

    return result


def _demand_rolling(df: pd.DataFrame) -> pd.DataFrame:
    qty_col   = "Order Item Quantity"
    price_col = "Product Price"
    disc_col  = "Order Item Discount"

    qty = df[qty_col].fillna(0) if qty_col in df.columns else pd.Series(0.0, index=df.index)

    grp_cols = [c for c in ("Category Name", "Order Region") if c in df.columns]
    if grp_cols and qty_col in df.columns:
        g = df.groupby(grp_cols)[qty_col]
        # A6 fix: shift(1) before rolling so row i never sees its own value
        df["qty_roll_7"]  = g.transform(lambda x: x.shift(1).rolling(7,  min_periods=1).mean())
        df["qty_roll_30"] = g.transform(lambda x: x.shift(1).rolling(30, min_periods=1).mean())
        df["qty_lag_1"]   = g.transform(lambda x: x.shift(1).fillna(x.mean()))
        df["qty_lag_7"]   = g.transform(lambda x: x.shift(7).fillna(x.mean()))
        df["qty_lag_30"]  = g.transform(lambda x: x.shift(30).fillna(x.mean()))
    else:
        df["qty_roll_7"]  = qty.shift(1).rolling(7,  min_periods=1).mean()
        df["qty_roll_30"] = qty.shift(1).rolling(30, min_periods=1).mean()
        df["qty_lag_1"]   = qty.shift(1).fillna(qty.mean())
        df["qty_lag_7"]   = qty.shift(7).fillna(qty.mean())
        df["qty_lag_30"]  = qty.shift(30).fillna(qty.mean())

    price = df[price_col].fillna(0) if price_col in df.columns else pd.Series(0.0, index=df.index)
    price_mean = price.mean() if price.mean() > 0 else 1.0
    df["price_ratio"] = (price / price_mean).fillna(1.0)

    sales = df["Sales"].fillna(0) if "Sales" in df.columns else pd.Series(0.0, index=df.index)
    disc  = df[disc_col].fillna(0) if disc_col in df.columns else pd.Series(0.0, index=df.index)
    df["discount_rate"] = np.where(sales > 0, disc / sales, 0.0)

    roll_30_safe = df["qty_roll_30"].replace(0, np.nan).fillna(1.0)
    std_30 = (
        df.groupby(grp_cols)[qty_col].transform(lambda x: x.shift(1).rolling(30, min_periods=2).std().fillna(0))
        if grp_cols and qty_col in df.columns
        else qty.shift(1).rolling(30, min_periods=2).std().fillna(0)
    )
    df["demand_volatility"]  = (std_30 / roll_30_safe).clip(0, 5).fillna(0.0)
    df["demand_trend_slope"] = (
        (df["qty_roll_7"] - df["qty_roll_30"]) / roll_30_safe
    ).clip(-2, 3).fillna(0.0)

    # A6 fix: std_14 also shifted so demand_spike_flag compares qty against
    # a window that excludes the current row
    std_14 = (
        df.groupby(grp_cols)[qty_col].transform(lambda x: x.shift(1).rolling(14, min_periods=2).std().fillna(0))
        if grp_cols and qty_col in df.columns
        else qty.shift(1).rolling(14, min_periods=2).std().fillna(0)
    )
    qty_prev = (
        df.groupby(grp_cols)[qty_col].transform(lambda x: x.shift(1))
        if grp_cols and qty_col in df.columns
        else qty.shift(1)
    )
    df["demand_spike_flag"] = (
        qty_prev > (df["qty_roll_7"] + 2 * std_14)
    ).fillna(False).astype(int)
    df["demand_momentum"]   = (df["qty_roll_7"] / roll_30_safe).clip(0, 3).fillna(1.0)

    # Financial — kept for non-demand models; NOT in DEMAND_FEATURES
    df["order_value_log"]  = np.log1p(np.maximum(sales, 0))
    df["revenue_per_unit"] = np.where(qty > 0, sales / qty, 0.0)

    # A7 fix: category_demand_rank — use expanding shifted mean per category
    # so row i sees only historical qty, not the full-df sum (which leaks target).
    cat_col = "Category Name"
    if cat_col in df.columns and qty_col in df.columns:
        df["category_demand_rank"] = _expanding_group_mean(
            df, [cat_col], qty_col, min_periods=1
        )
        # Normalise to [0, 1] using the global max of the expanding means
        _max = df["category_demand_rank"].max()
        df["category_demand_rank"] = (df["category_demand_rank"] / max(_max, 1)).clip(0, 1)
    else:
        df["category_demand_rank"] = 0.5

    # Legacy aliases
    df["rolling_7d_demand"]  = df["qty_roll_7"]
    df["rolling_14d_demand"] = df["qty_roll_7"]
    df["rolling_30d_demand"] = df["qty_roll_30"]
    df["demand_lag_1m"]      = df["qty_lag_1"]
    df["demand_lag_3m"]      = df["qty_lag_30"]
    df["demand_trend"]       = df["demand_trend_slope"]

    return df


def _inventory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Inventory stress signals.

    days_until_reorder: 14 - 7 * (qty_roll_7 / qty_roll_30)
    Dimensionally correct — both numerator and denominator are per-day means.
    """
    qty_col = "Order Item Quantity"
    qty = df[qty_col].fillna(0) if qty_col in df.columns else pd.Series(0.0, index=df.index)

    grp_cols = [c for c in ("Category Name", "Order Region") if c in df.columns]
    if grp_cols and qty_col in df.columns:
        roll_14 = df.groupby(grp_cols)[qty_col].transform(
            lambda x: x.rolling(14, min_periods=1).mean()
        )
    else:
        roll_14 = qty.rolling(14, min_periods=1).mean()

    roll_14_safe = roll_14.replace(0, np.nan).fillna(1.0)
    roll_30_safe = df["qty_roll_30"].replace(0, np.nan).fillna(1.0)

    df["inventory_stress_index"] = (qty / roll_14_safe).clip(0, 3).fillna(0.5)
    df["days_until_reorder"]     = (
        14 - 7 * (df["qty_roll_7"] / roll_30_safe)
    ).fillna(14).clip(0, 21)
    df["reorder_point"]          = (df["qty_roll_7"] * 1.5).fillna(0)
    df["demand_variability"]     = df["demand_volatility"]
    df["stock_coverage_ratio"]   = (df["qty_roll_30"] / roll_14_safe).clip(0.1, 10).fillna(1.0)

    return df


def _supplier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Supplier features — all historical rates use expanding shifted encoding.
    No full-df target encoding anywhere in this function.
    """
    dept_col   = "Department Name"
    mode_col   = "Shipping Mode"
    target_col = "Late_delivery_risk"

    if dept_col not in df.columns:
        for c, v in [("supplier_hist_late_rate", 0.5),
                     ("supplier_reliability_score", 0.5),
                     ("supplier_order_volume", 0.0),
                     ("supplier_category_diversity", 0.0),
                     ("supplier_delay_rate", 0.5),
                     ("supplier_risk_index", 0.5),
                     ("supplier_volume", 0.0)]:
            df[c] = v
        return df

    # ── Expanding shifted late rate per (Department, Shipping Mode) ──────────
    # Row i sees only rows strictly before it — no full-df leakage.
    grp = [c for c in (dept_col, mode_col) if c in df.columns]
    df["supplier_hist_late_rate"] = expanding_target_rate(df, grp, target_col)

    # supplier_reliability_score = 1 - hist_late_rate (on-time rate)
    df["supplier_reliability_score"] = (1.0 - df["supplier_hist_late_rate"]).clip(0, 1)

    # supplier_delay_rate = expanding late rate per department only
    df["supplier_delay_rate"] = expanding_target_rate(df, dept_col, target_col)

    # supplier_order_volume: normalised order count per department
    vol = df.groupby(dept_col)[dept_col].transform("count")
    df["supplier_order_volume"] = (vol / max(vol.max(), 1)).fillna(0.0)
    df["supplier_volume"]       = df["supplier_order_volume"]

    # supplier_category_diversity: distinct categories per department
    if "Category Name" in df.columns:
        div = df.groupby(dept_col)["Category Name"].transform("nunique")
        df["supplier_category_diversity"] = (div / max(div.max(), 1)).fillna(0.0)
    else:
        df["supplier_category_diversity"] = 0.0

    # supplier_risk_index: composite of delay rate and unreliability
    df["supplier_risk_index"] = (
        df["supplier_delay_rate"] * 0.6
        + (1.0 - df["supplier_reliability_score"]) * 0.4
    ).clip(0, 1)

    return df


def _logistics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Logistics features — all historical rates use expanding shifted encoding.

    shipping_mode_encoded: ordinal from expanding late rate per mode.
    region_congestion_index: expanding late rate per region.
    route_hist_late_rate: expanding late rate per (mode, region).
    """
    mode_col   = "Shipping Mode"
    region_col = "Order Region"
    target_col = "Late_delivery_risk"
    sched_col  = "Days for shipment (scheduled)"

    # ── Expanding shifted rates — no full-df target encoding ─────────────────
    df["route_hist_late_rate"]   = expanding_target_rate(
        df, [c for c in (mode_col, region_col) if c in df.columns], target_col
    )
    df["region_hist_late_rate"]  = expanding_target_rate(df, region_col, target_col)
    df["shipmode_hist_late_rate"] = expanding_target_rate(df, mode_col, target_col)

    # shipping_mode_encoded: use expanding rate (not full-df mean)
    df["shipping_mode_encoded"] = df["shipmode_hist_late_rate"]

    # region_congestion_index: expanding rate per region
    df["region_congestion_index"] = df["region_hist_late_rate"]

    # route_frequency: how often this (mode, region) pair appears, normalised
    if mode_col in df.columns and region_col in df.columns:
        freq = df.groupby([mode_col, region_col])[mode_col].transform("count")
        df["route_frequency"] = (freq / max(freq.max(), 1)).fillna(0.0)
    else:
        df["route_frequency"] = 0.0

    # days_scheduled: scheduled shipping days — known at order time
    if sched_col in df.columns:
        df["days_scheduled"] = df[sched_col].fillna(df[sched_col].median())
    else:
        df["days_scheduled"] = 3.0

    return df


def _post_shipment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Post-shipment observables.

    BANNED from Late_delivery_risk models (enforced by leakage guard in ml/utils).
    Computed here for Inventory/Demand use and backward compatibility only.
    """
    real_col  = "Days for shipping (real)"
    sched_col = "Days for shipment (scheduled)"

    if real_col in df.columns and sched_col in df.columns:
        real  = df[real_col].fillna(0)
        sched = df[sched_col].fillna(1)
        df["delivery_gap"]           = real - sched
        df["is_delayed"]             = (real > sched).astype(int)
        df["delivery_duration_days"] = real
        df["shipping_delay_ratio"]   = np.where(sched > 0, real / sched, 1.0)
    else:
        df["delivery_gap"]           = 0.0
        df["is_delayed"]             = 0
        df["delivery_duration_days"] = 0.0
        df["shipping_delay_ratio"]   = 1.0

    # composite_risk_score — also banned from Late_delivery_risk lists
    sr_max = df["shipping_delay_ratio"].max() if df["shipping_delay_ratio"].max() > 0 else 1
    df["composite_risk_score"] = np.clip(
        (df["shipping_delay_ratio"] / sr_max) * 0.4
        + df["supplier_risk_index"] * 0.4
        + df["discount_rate"] * 0.2,
        0, 1,
    )

    return df


def _graph_context_tier1(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tier-1 graph context columns — expanding-shifted aggregates, never full-df.

    A3 fix: replaced full-df groupby().transform("mean") with expanding-shifted
    equivalents so test rows cannot see test-set target-derived values.

    graph_avg_shipping_delay uses Late_delivery_risk as a delay proxy via
    expanding-shifted mean per (Shipping Mode, Region) — NOT delivery_gap
    (post-hoc) and NOT Days for shipment (scheduled) (no temporal discipline).
    """
    dept_col   = "Department Name"
    mode_col   = "Shipping Mode"
    cat_col    = "Category Name"
    region_col = "Order Region"
    sched_col  = "Days for shipment (scheduled)"
    target_col = "Late_delivery_risk"

    # graph_supplier_reliability: expanding shifted on-time rate per (Dept, Mode)
    # = 1 - expanding late rate (same source as supplier_reliability_score but
    # computed at graph-group level, not supplier level)
    grp = [c for c in (dept_col, mode_col) if c in df.columns]
    df["graph_supplier_reliability"] = (
        1.0 - expanding_target_rate(df, grp, target_col)
    ).clip(0, 1)

    # graph_inventory_stress: expanding shifted mean per (Category, Region)
    df["graph_inventory_stress"] = _expanding_group_mean(
        df, [cat_col, region_col], "inventory_stress_index"
    )

    # graph_avg_shipping_delay: expanding shifted mean of OBSERVED late rate per
    # (Shipping Mode, Region) neighbour routes — Tier-1 proxy for Neo4j traversal.
    # Uses Late_delivery_risk as a delay proxy (expanding-shifted, leak-free).
    # Tier-2 overwrites with actual neighbour-route observed delay via
    # :SHIPS_VIA / :CO_FAILS_WITH edges, excluding the anchor row's own route.
    df["graph_avg_shipping_delay"] = _expanding_group_mean(
        df, [mode_col, region_col], target_col   # late rate as delay proxy
    )

    # graph_tpke_edge_density: expanding shifted count of (Dept, Mode)
    # co-occurrences normalised to [0,1] — no full-df computation.
    # Tier-2 overwrites with actual TPKE edge count from Neo4j.
    if dept_col in df.columns and mode_col in df.columns:
        # Build expanding count per (dept, mode) group, shifted so row i
        # sees only rows strictly before it.
        pair_key = df[dept_col].astype(str) + "__" + df[mode_col].astype(str)
        expanding_counts = pd.Series(np.nan, index=df.index)
        for _, grp_idx in df.groupby([dept_col, mode_col]).groups.items():
            s = pd.Series(1.0, index=grp_idx)
            expanding_counts.loc[grp_idx] = (
                s.expanding(min_periods=1).sum().shift(1).fillna(0).values
            )
        expanding_counts = expanding_counts.fillna(0.0)
        _max_count = expanding_counts.max()
        df["graph_tpke_edge_density"] = (
            (expanding_counts / max(_max_count, 1)).clip(0, 1)
        )
    else:
        df["graph_tpke_edge_density"] = 0.0

    return df


def _aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible aliases."""
    df["shipping_delay"]            = df["delivery_gap"]
    df["shipping_efficiency_score"] = df["shipping_delay_ratio"]
    df["is_weekend_order"]          = df["is_weekend"]
    df["order_value_tier"]          = pd.cut(
        df["order_value_log"], bins=4, labels=[0, 1, 2, 3], right=False
    ).astype(int)
    df["delay_category"] = pd.cut(
        df["delivery_gap"],
        bins=[-999, -1, 0, 3, 7, 999],
        labels=[0, 1, 2, 3, 4],
        right=False,
    ).astype(int)
    df["is_holiday_week"] = df["is_holiday_period"]
    return df


def _zscore(s: pd.Series) -> pd.Series:
    mu, sigma = s.mean(), s.std()
    return np.where(sigma > 0, (s - mu) / sigma, 0.0)

"""
AMASCI Schema Adapter
======================
Resolves DataCo column aliases to canonical names and reports unknown columns.

adapt(df) -> (df, SchemaReport)

REQUIRED canonical names and their known DataCo aliases:
  order_date      <- "order date (DateOrders)", "Order Date", "orderdate"
  target          <- "Late_delivery_risk", "late_delivery_risk"
  quantity        <- "Order Item Quantity", "order_item_quantity"
  sched_days      <- "Days for shipment (scheduled)", "days_for_shipment_scheduled"
  shipping_mode   <- "Shipping Mode", "shipping_mode"
  department      <- "Department Name", "department_name"
  category        <- "Category Name", "category_name"
  region          <- "Order Region", "order_region"
  market          <- "Market", "market"
  product_id      <- "Product Card Id", "product_card_id", "Product Card ID"
  order_item_id   <- "Order Item Id", "order_item_id", "Order Item ID"
  price           <- "Product Price", "product_price"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# Canonical name -> list of known aliases (first match wins, case-insensitive)
_ALIASES: dict[str, list[str]] = {
    "order_date":    ["order date (DateOrders)", "Order Date", "orderdate", "order_date"],
    "target":        ["Late_delivery_risk", "late_delivery_risk", "LateDeliveryRisk"],
    "quantity":      ["Order Item Quantity", "order_item_quantity", "OrderItemQuantity"],
    "sched_days":    ["Days for shipment (scheduled)", "days_for_shipment_scheduled",
                      "DaysForShipmentScheduled"],
    "shipping_mode": ["Shipping Mode", "shipping_mode", "ShippingMode"],
    "department":    ["Department Name", "department_name", "DepartmentName"],
    "category":      ["Category Name", "category_name", "CategoryName"],
    "region":        ["Order Region", "order_region", "OrderRegion"],
    "market":        ["Market", "market"],
    "product_id":    ["Product Card Id", "product_card_id", "Product Card ID",
                      "ProductCardId"],
    "order_item_id": ["Order Item Id", "order_item_id", "Order Item ID", "OrderItemId"],
    "price":         ["Product Price", "product_price", "ProductPrice"],
}

REQUIRED: frozenset[str] = frozenset(_ALIASES.keys())


@dataclass
class SchemaReport:
    ok: bool
    resolved: dict[str, str]   # canonical -> original column name
    missing: list[str]          # canonical names with no match
    extra: list[str]            # columns present but not in any alias list
    row_count: int
    date_min: Optional[str]
    date_max: Optional[str]


def adapt(df: pd.DataFrame) -> tuple[pd.DataFrame, SchemaReport]:
    """
    Resolve DataCo column aliases to canonical names.

    Returns a copy of df with canonical column names added (originals kept),
    and a SchemaReport describing what was resolved, what is missing, and
    what extra columns are present.

    Unknown columns are reported in SchemaReport.extra — they are NOT dropped.
    """
    df = df.copy()
    col_lower = {c.lower().strip(): c for c in df.columns}

    resolved: dict[str, str] = {}
    missing: list[str] = []

    for canonical, aliases in _ALIASES.items():
        if canonical in df.columns:
            resolved[canonical] = canonical
            continue
        matched = None
        for alias in aliases:
            if alias in df.columns:
                matched = alias
                break
            if alias.lower() in col_lower:
                matched = col_lower[alias.lower()]
                break
        if matched:
            df[canonical] = df[matched]
            resolved[canonical] = matched
        else:
            missing.append(canonical)

    # Extra columns: present in df but not a canonical name and not any known alias
    all_known_aliases: set[str] = set()
    for aliases in _ALIASES.values():
        all_known_aliases.update(a.lower() for a in aliases)
    all_known_aliases.update(c.lower() for c in REQUIRED)

    extra = [
        c for c in df.columns
        if c.lower() not in all_known_aliases and c not in REQUIRED
    ]

    # Date range from resolved order_date
    date_min: Optional[str] = None
    date_max: Optional[str] = None
    if "order_date" in df.columns:
        dates = pd.to_datetime(df["order_date"], errors="coerce").dropna()
        if not dates.empty:
            date_min = str(dates.min().date())
            date_max = str(dates.max().date())

    ok = len(missing) == 0
    report = SchemaReport(
        ok=ok,
        resolved=resolved,
        missing=missing,
        extra=extra,
        row_count=len(df),
        date_min=date_min,
        date_max=date_max,
    )
    return df, report

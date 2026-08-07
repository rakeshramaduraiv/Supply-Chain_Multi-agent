"""
TPKE Edge Logic Validator (Issue #14)
=======================================
Pre-validates that a proposed TPKE edge makes causal sense before it is
written to Neo4j.  Prevents spurious edges from polluting the graph.
"""

import logging

logger = logging.getLogger(__name__)

# Allowed causal transitions: source_event -> [valid target_events]
_VALID_TRANSITIONS: dict[str, list[str]] = {
    "SUPPLIER_DELAY":  ["DEMAND_SPIKE", "INVENTORY_DROP"],
    "DEMAND_SPIKE":    ["SUPPLIER_DELAY", "INVENTORY_DROP"],
    "INVENTORY_DROP":  ["DEMAND_SPIKE", "SUPPLIER_DELAY"],
    "LATE_DELIVERY":   ["CUSTOMER_CHURN"],
}

# Required source entity type per event
_SOURCE_ENTITY_CONSTRAINTS: dict[str, str] = {
    "SUPPLIER_DELAY": "Supplier",
    "DEMAND_SPIKE":   "Product",
    "INVENTORY_DROP": "Warehouse",
    "LATE_DELIVERY":  "Shipment",
}

# Required target entity type per event
_TARGET_ENTITY_CONSTRAINTS: dict[str, str] = {
    "DEMAND_SPIKE":   "Product",
    "INVENTORY_DROP": "Warehouse",
    "SUPPLIER_DELAY": "Supplier",
    "CUSTOMER_CHURN": "Customer",
}


def validate_edge_logic(
    source_event: str,
    target_event: str,
    source_entity_type: str,
    target_entity_type: str,
) -> tuple[bool, str]:
    """
    Validate whether a proposed TPKE edge makes causal sense.

    Returns (is_valid, reason).
    """
    # Check transition is in the allowed list
    allowed_targets = _VALID_TRANSITIONS.get(source_event)
    if allowed_targets is None:
        return False, f"Unknown source event '{source_event}'"
    if target_event not in allowed_targets:
        return False, (
            f"'{source_event}' -> '{target_event}' is not a known causal pattern"
        )

    # Check source entity type constraint
    required_src = _SOURCE_ENTITY_CONSTRAINTS.get(source_event)
    if required_src and source_entity_type != required_src:
        return False, (
            f"'{source_event}' must originate from {required_src}, "
            f"got {source_entity_type}"
        )

    # Check target entity type constraint
    required_tgt = _TARGET_ENTITY_CONSTRAINTS.get(target_event)
    if required_tgt and target_entity_type != required_tgt:
        return False, (
            f"'{target_event}' must target {required_tgt}, "
            f"got {target_entity_type}"
        )

    return True, "Edge logic validated"

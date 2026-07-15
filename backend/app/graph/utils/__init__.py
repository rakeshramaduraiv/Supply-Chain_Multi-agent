"""
AMASCI Graph Utilities
========================
Shared constants, Cypher templates, and helper functions.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# --- Batch Processing Constants ---
DEFAULT_BATCH_SIZE = 500
MAX_BATCH_SIZE = 5000

# --- Node Labels ---
NODE_LABELS = [
    "Supplier", "Product", "Warehouse", "Shipment",
    "Customer", "Order", "CalendarEvent",
]

# --- Relationship Types ---
RELATIONSHIP_TYPES = [
    "SUPPLIES", "STORED_IN", "SHIPS_VIA",
    "DELIVERED_TO", "PLACED", "CONTAINS", "INFLUENCES",
]


def generate_node_id(label: str, *keys: Any) -> str:
    """Generate a deterministic node ID from label and key values."""
    raw = f"{label}:{'|'.join(str(k) for k in keys)}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def utc_now_iso() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        result = float(value)
        if result != result:  # NaN check
            return default
        return result
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string."""
    if value is None:
        return default
    s = str(value).strip()
    return s if s and s.lower() != "nan" else default


def build_set_clause(properties: dict[str, Any], alias: str = "n") -> str:
    """Build a Cypher SET clause from a properties dict."""
    parts = []
    for key in properties:
        parts.append(f"{alias}.{key} = ${key}")
    return ", ".join(parts)


def chunk_list(items: list, chunk_size: int = DEFAULT_BATCH_SIZE) -> list[list]:
    """Split a list into chunks for batch processing."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

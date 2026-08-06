"""
AMASCI Graph Utilities
========================
Shared constants, Cypher templates, and helper functions.
"""

import hashlib
import logging
import math
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
    """Safely convert value to float. Rejects NaN and Inf (Neo4j rejects both)."""
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        if value is None:
            return default
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string."""
    if value is None:
        return default
    s = str(value).strip()
    return s if s and s.lower() != "nan" else default


def safe_params(params: dict) -> dict:
    """Sanitize an entire Cypher parameter dict — Neo4j driver rejects NaN/Inf."""
    out = {}
    for k, v in params.items():
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, float):
            out[k] = safe_float(v)
        elif isinstance(v, int):
            out[k] = safe_int(v)
        elif isinstance(v, (str, list, dict)) or v is None:
            out[k] = v
        else:
            out[k] = safe_str(v)
    return out


def build_set_clause(properties: dict[str, Any], alias: str = "n") -> str:
    """Build a Cypher SET clause from a properties dict."""
    parts = []
    for key in properties:
        parts.append(f"{alias}.{key} = ${key}")
    return ", ".join(parts)


def chunk_list(items: list, chunk_size: int = DEFAULT_BATCH_SIZE) -> list[list]:
    """Split a list into chunks for batch processing."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

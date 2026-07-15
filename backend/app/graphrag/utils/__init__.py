"""
AMASCI GraphRAG Utilities
===========================
Shared helpers for the GraphRAG module.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def generate_context_id(prefix: str, *args: str) -> str:
    """Generate a deterministic context ID."""
    raw = f"{prefix}:{'|'.join(args)}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def utc_now() -> datetime:
    """Current UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Current UTC as ISO string."""
    return utc_now().isoformat()


def safe_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get a nested key using dot notation."""
    keys = key.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k, default)
        else:
            return default
    return current


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def flatten_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested properties for embedding input."""
    flat: dict[str, Any] = {}
    for key, value in props.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}_{sub_key}"] = sub_value
        elif isinstance(value, list):
            flat[key] = str(value)
        else:
            flat[key] = value
    return flat


def compute_risk_label(score: float) -> str:
    """Convert numeric risk score to categorical label."""
    if score >= 0.75:
        return "critical"
    elif score >= 0.50:
        return "high"
    elif score >= 0.25:
        return "medium"
    return "low"


def normalize_score(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp and normalize a score to [0, 1]."""
    if max_val == min_val:
        return 0.0
    clamped = max(min_val, min(max_val, value))
    return (clamped - min_val) / (max_val - min_val)


def build_node_signature(label: str, properties: dict[str, Any]) -> str:
    """Build a text signature for a node (for embedding)."""
    parts = [f"[{label}]"]
    for key, value in sorted(properties.items()):
        if key in ("created_at", "updated_at", "node_id"):
            continue
        if value is not None and value != "" and value != 0:
            parts.append(f"{key}={value}")
    return " | ".join(parts)


class PerformanceTimer:
    """Context manager for timing operations with logging."""

    def __init__(self, operation: str):
        self.operation = operation
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        logger.debug(f"[GraphRAG] {self.operation}: {self.duration_ms:.2f}ms")

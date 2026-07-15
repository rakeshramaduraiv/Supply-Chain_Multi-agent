"""
AMASCI RCA Utilities
======================
Shared helpers for the Root Cause Analysis module.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RCAType(str, Enum):
    """Supported RCA disruption types."""
    LATE_DELIVERY = "late_delivery"
    INVENTORY_STRESS = "inventory_stress"
    DEMAND_SPIKE = "demand_spike"
    SUPPLIER_FAILURE = "supplier_failure"
    WAREHOUSE_CONGESTION = "warehouse_congestion"
    SHIPPING_DELAY = "shipping_delay"
    CUSTOMER_COMPLAINT = "customer_complaint"


# Weights for risk contribution formula
ALPHA = 0.30  # Node risk weight
BETA = 0.25   # Relationship weight
GAMMA = 0.20  # TPKE edge weight
DELTA = 0.15  # Centrality score weight
EPSILON = 0.10  # Forecast confidence weight

RISK_PROPAGATION_DECAY = 0.7
MAX_TRAVERSAL_DEPTH = 5
MAX_CAUSAL_CHAIN_LENGTH = 8


def generate_rca_id(entity_id: str, rca_type: str) -> str:
    """Generate a unique RCA report ID."""
    raw = f"rca:{entity_id}:{rca_type}:{utc_now_iso()}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def compute_risk_label(score: float) -> str:
    """Convert numeric risk score to categorical label."""
    if score >= 0.75:
        return "critical"
    elif score >= 0.50:
        return "high"
    elif score >= 0.25:
        return "medium"
    return "low"


def normalize_scores(scores: list[float]) -> list[float]:
    """Min-max normalize a list of scores to [0, 1]."""
    if not scores:
        return []
    min_val = min(scores)
    max_val = max(scores)
    if max_val == min_val:
        return [0.5] * len(scores)
    return [(s - min_val) / (max_val - min_val) for s in scores]


def extract_node_risk(properties: dict[str, Any]) -> float:
    """Extract the primary risk score from node properties."""
    risk_fields = [
        "risk_score", "late_delivery_rate", "warehouse_risk",
        "forecast_risk", "supplier_delay_rate", "inventory_stress",
    ]
    for field in risk_fields:
        val = properties.get(field)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return 0.0


def extract_relationship_weight(properties: dict[str, Any]) -> float:
    """Extract relationship strength/weight."""
    for field in ("relationship_strength", "weight", "strength"):
        val = properties.get(field)
        if isinstance(val, (int, float)):
            return float(val)
    return 0.5


class PerformanceTimer:
    """Context manager for timing RCA operations."""

    def __init__(self, operation: str):
        self.operation = operation
        self.start_time: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        logger.debug(f"[RCA] {self.operation}: {self.duration_ms:.2f}ms")

"""
TPKE Pattern Detector
======================
Sliding-window temporal pattern detection with conditional probability scoring.

Detects co-occurrence patterns between supply chain entities (suppliers, products,
regions, shipping modes) that repeatedly appear together in deviation events.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DeviationEvent:
    """A single forecast-vs-actual deviation event."""
    event_id: str
    timestamp: datetime
    entity_id: str
    entity_type: str
    predicted_value: float
    actual_value: float
    deviation: float  # actual - predicted
    deviation_pct: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CoOccurrence:
    """A detected co-occurrence between two entities."""
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    frequency: int
    conditional_probability: float
    temporal_score: float
    timestamps: list[datetime] = field(default_factory=list)


@dataclass
class TemporalPattern:
    """A validated temporal pattern that qualifies for graph evolution."""
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relationship_type: str
    weight: float  # Combined score: α·confidence + β·frequency + γ·temporal
    confidence: float
    frequency: int
    temporal_score: float
    evidence: dict[str, Any] = field(default_factory=dict)


class PatternDetector:
    """
    Detects temporal co-occurrence patterns from deviation events.

    Algorithm:
    1. Collect deviation events within sliding window
    2. Group events by time buckets (daily)
    3. Compute pairwise co-occurrence frequencies
    4. Calculate conditional probability P(B|A)
    5. Score temporal regularity (how evenly distributed across time)
    6. Filter by frequency threshold and confidence threshold
    """

    def __init__(
        self,
        window_size_days: int = 90,
        frequency_threshold: int = 3,
        confidence_threshold: float = 0.6,
        alpha: float = 0.4,
        beta: float = 0.35,
        gamma: float = 0.25,
    ):
        self._window_days = window_size_days
        self._freq_threshold = frequency_threshold
        self._conf_threshold = confidence_threshold
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma

    def detect_patterns(
        self,
        events: list[DeviationEvent],
        reference_time: datetime | None = None,
    ) -> list[TemporalPattern]:
        """
        Main entry: detect all qualifying temporal patterns from events.

        Returns list of TemporalPattern objects ready for graph evolution.
        """
        if not events:
            return []

        ref_time = reference_time or datetime.now(timezone.utc)
        window_start = ref_time - timedelta(days=self._window_days)

        # Filter to window
        windowed = [e for e in events if e.timestamp >= window_start]
        if len(windowed) < self._freq_threshold:
            logger.info(f"Insufficient events in window: {len(windowed)}")
            return []

        # Group by daily buckets
        buckets = self._bucket_events(windowed)

        # Compute co-occurrences
        co_occurrences = self._compute_co_occurrences(buckets)

        # Score and filter
        patterns = self._score_and_filter(co_occurrences, len(buckets))

        logger.info(f"Detected {len(patterns)} temporal patterns from {len(windowed)} events")
        return patterns

    def _bucket_events(self, events: list[DeviationEvent]) -> dict[str, list[DeviationEvent]]:
        """Group events into daily buckets."""
        buckets: dict[str, list[DeviationEvent]] = defaultdict(list)
        for event in events:
            key = event.timestamp.strftime("%Y-%m-%d")
            buckets[key].append(event)
        return buckets

    def _compute_co_occurrences(
        self, buckets: dict[str, list[DeviationEvent]]
    ) -> list[CoOccurrence]:
        """Compute pairwise entity co-occurrence across time buckets."""
        # Count how many buckets each entity appears in
        entity_bucket_count: dict[str, int] = defaultdict(int)
        # Count how many buckets each pair co-occurs in
        pair_bucket_count: dict[tuple[str, str], int] = defaultdict(int)
        # Track timestamps for each pair
        pair_timestamps: dict[tuple[str, str], list[datetime]] = defaultdict(list)

        for bucket_date, events in buckets.items():
            # Unique entities in this bucket
            entities = set()
            entity_map: dict[str, DeviationEvent] = {}
            for e in events:
                entity_key = f"{e.entity_type}:{e.entity_id}"
                entities.add(entity_key)
                entity_map[entity_key] = e

            for ek in entities:
                entity_bucket_count[ek] += 1

            # Pairwise co-occurrence within same bucket
            entity_list = sorted(entities)
            for i in range(len(entity_list)):
                for j in range(i + 1, len(entity_list)):
                    pair = (entity_list[i], entity_list[j])
                    pair_bucket_count[pair] += 1
                    ts = entity_map[entity_list[i]].timestamp
                    pair_timestamps[pair].append(ts)

        # Build CoOccurrence objects with conditional probability
        results: list[CoOccurrence] = []
        total_buckets = len(buckets)

        for (src_key, tgt_key), freq in pair_bucket_count.items():
            if freq < self._freq_threshold:
                continue

            src_type, src_id = src_key.split(":", 1)
            tgt_type, tgt_id = tgt_key.split(":", 1)

            # P(target | source) = co-occurrence / source_count
            src_count = entity_bucket_count[src_key]
            cond_prob = freq / src_count if src_count > 0 else 0.0

            # Temporal regularity: std of inter-event intervals (lower = more regular)
            timestamps = sorted(pair_timestamps[(src_key, tgt_key)])
            temporal_score = self._compute_temporal_regularity(timestamps, total_buckets)

            results.append(CoOccurrence(
                source_id=src_id,
                source_type=src_type,
                target_id=tgt_id,
                target_type=tgt_type,
                frequency=freq,
                conditional_probability=cond_prob,
                temporal_score=temporal_score,
                timestamps=timestamps,
            ))

        return results

    def _compute_temporal_regularity(self, timestamps: list[datetime], total_buckets: int) -> float:
        """
        Score temporal regularity [0, 1].
        Higher = more evenly distributed across the window (more reliable pattern).
        """
        if len(timestamps) < 2:
            return 0.5

        # Compute intervals between consecutive occurrences
        intervals = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).total_seconds() / 86400.0
            intervals.append(delta)

        if not intervals:
            return 0.5

        mean_interval = np.mean(intervals)
        if mean_interval == 0:
            return 1.0

        # Coefficient of variation (lower = more regular)
        cv = np.std(intervals) / mean_interval if mean_interval > 0 else 1.0

        # Convert to [0, 1] score where 1 = perfectly regular
        regularity = 1.0 / (1.0 + cv)

        # Bonus for spanning more of the window
        span_ratio = len(timestamps) / max(total_buckets, 1)
        span_bonus = min(span_ratio * 0.2, 0.2)

        return min(regularity + span_bonus, 1.0)

    def _score_and_filter(
        self, co_occurrences: list[CoOccurrence], total_buckets: int
    ) -> list[TemporalPattern]:
        """Apply weighted scoring formula and filter by confidence threshold."""
        patterns: list[TemporalPattern] = []

        # Normalize frequency to [0, 1]
        max_freq = max((c.frequency for c in co_occurrences), default=1)

        for co in co_occurrences:
            confidence = co.conditional_probability
            freq_normalized = co.frequency / max_freq if max_freq > 0 else 0.0
            temporal = co.temporal_score

            # w(e) = α·confidence + β·frequency + γ·temporal
            weight = (
                self._alpha * confidence
                + self._beta * freq_normalized
                + self._gamma * temporal
            )

            if weight < self._conf_threshold:
                continue

            # Determine relationship type based on entity types
            rel_type = self._infer_relationship_type(co.source_type, co.target_type)

            patterns.append(TemporalPattern(
                source_id=co.source_id,
                source_type=co.source_type,
                target_id=co.target_id,
                target_type=co.target_type,
                relationship_type=rel_type,
                weight=round(weight, 4),
                confidence=round(confidence, 4),
                frequency=co.frequency,
                temporal_score=round(temporal, 4),
                evidence={
                    "bucket_count": co.frequency,
                    "conditional_probability": round(confidence, 4),
                    "temporal_regularity": round(temporal, 4),
                    "first_seen": co.timestamps[0].isoformat() if co.timestamps else None,
                    "last_seen": co.timestamps[-1].isoformat() if co.timestamps else None,
                },
            ))

        # Sort by weight descending
        patterns.sort(key=lambda p: p.weight, reverse=True)
        return patterns

    @staticmethod
    def _infer_relationship_type(source_type: str, target_type: str) -> str:
        """Infer the Neo4j relationship type from entity type pair."""
        pair = (source_type, target_type)
        mapping = {
            ("Supplier", "Product"): "SUPPLIES",
            ("Product", "Supplier"): "SUPPLIES",
            ("Product", "Warehouse"): "STORED_IN",
            ("Warehouse", "Product"): "STORED_IN",
            ("Supplier", "Warehouse"): "SHIPS_VIA",
            ("Warehouse", "Supplier"): "SHIPS_VIA",
            ("Order", "Customer"): "PLACED",
            ("Customer", "Order"): "PLACED",
            ("Shipment", "Customer"): "DELIVERED_TO",
            ("Customer", "Shipment"): "DELIVERED_TO",
            ("Order", "Product"): "CONTAINS",
            ("Product", "Order"): "CONTAINS",
        }
        return mapping.get(pair, "INFLUENCES")

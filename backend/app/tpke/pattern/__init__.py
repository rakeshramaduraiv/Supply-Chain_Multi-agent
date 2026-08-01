"""
TPKE Pattern Detector
======================
Detects CAUSAL SEQUENTIAL patterns from deviation events.

The algorithm:

    1. Classify each deviation event into a named event type
       (LATE_DELIVERY, INVENTORY_DROP, DEMAND_SPIKE, SUPPLIER_DELAY, STOCKOUT)

    2. Within the sliding window W, scan for sequences:
           Event A on Day T  →  Event B on Day T+delta (delta <= lag_days)

    3. Count how many times each (A → B) sequence occurs  →  frequency

    4. Apply K gate: frequency must be >= K (minimum observations)

    5. Compute conditional probability:
           P(B | A) = count(A then B) / count(A)

    6. Apply θ gate: P(B | A) must be >= θ (confidence threshold)

    7. Score temporal regularity of the sequence across the window

    8. Compute final edge weight:
           w = α·P(B|A) + β·(freq/max_freq) + γ·temporal_score

    9. Return TemporalPattern objects ready for graph evolution

Example output:
    LATE_DELIVERY  ──0.85──►  INVENTORY_DROP
    INVENTORY_DROP ──0.72──►  STOCKOUT
    DEMAND_SPIKE   ──0.68──►  SUPPLIER_DELAY
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ─── Event type classification ────────────────────────────────────────────────

# Maps (entity_type, deviation_direction) → named event type
# deviation_direction: "over" = actual > predicted, "under" = actual < predicted
_EVENT_TYPE_MAP: dict[tuple[str, str], str] = {
    ("Supplier",  "over"):  "SUPPLIER_DELAY",
    ("Supplier",  "under"): "SUPPLIER_IMPROVEMENT",
    ("Product",   "over"):  "DEMAND_SPIKE",
    ("Product",   "under"): "DEMAND_DROP",
    ("Warehouse", "over"):  "INVENTORY_STRESS",
    ("Warehouse", "under"): "INVENTORY_DROP",
    ("Shipment",  "over"):  "LATE_DELIVERY",
    ("Shipment",  "under"): "EARLY_DELIVERY",
    ("Order",     "over"):  "ORDER_SURGE",
    ("Order",     "under"): "ORDER_DECLINE",
    ("Customer",  "over"):  "COMPLAINT_SPIKE",
    ("Customer",  "under"): "SATISFACTION_GAIN",
}

# Causal relationship label for each (source_event → target_event) pair
# These become the Neo4j relationship type on the TPKE-inferred edge
_CAUSAL_RELATIONSHIP_MAP: dict[tuple[str, str], str] = {
    ("LATE_DELIVERY",    "INVENTORY_DROP"):    "LATE_DELIVERY_TRIGGERS_STOCKOUT",
    ("LATE_DELIVERY",    "COMPLAINT_SPIKE"):   "LATE_DELIVERY_CAUSES_COMPLAINT",
    ("LATE_DELIVERY",    "INVENTORY_STRESS"):  "LATE_DELIVERY_TRIGGERS_STOCKOUT",
    ("INVENTORY_DROP",   "COMPLAINT_SPIKE"):   "STOCKOUT_CAUSES_COMPLAINT",
    ("INVENTORY_DROP",   "ORDER_DECLINE"):     "STOCKOUT_SUPPRESSES_ORDERS",
    ("DEMAND_SPIKE",     "SUPPLIER_DELAY"):    "DEMAND_SPIKE_AMPLIFIES_SUPPLIER_RISK",
    ("DEMAND_SPIKE",     "INVENTORY_DROP"):    "DEMAND_SPIKE_DEPLETES_INVENTORY",
    ("DEMAND_SPIKE",     "INVENTORY_STRESS"):  "DEMAND_SPIKE_DEPLETES_INVENTORY",
    ("SUPPLIER_DELAY",   "INVENTORY_DROP"):    "SUPPLIER_DELAY_CAUSES_STOCKOUT",
    ("SUPPLIER_DELAY",   "INVENTORY_STRESS"):  "SUPPLIER_DELAY_CAUSES_STOCKOUT",
    ("SUPPLIER_DELAY",   "LATE_DELIVERY"):     "SUPPLIER_DELAY_CASCADES_TO_DELIVERY",
    ("INVENTORY_STRESS", "LATE_DELIVERY"):     "INVENTORY_STRESS_DELAYS_SHIPMENT",
    ("INVENTORY_STRESS", "COMPLAINT_SPIKE"):   "INVENTORY_STRESS_CAUSES_COMPLAINT",
    ("ORDER_SURGE",      "INVENTORY_STRESS"):  "ORDER_SURGE_STRESSES_INVENTORY",
    ("ORDER_SURGE",      "SUPPLIER_DELAY"):    "ORDER_SURGE_OVERLOADS_SUPPLIER",
}


def _classify_event(entity_type: str, deviation: float) -> str:
    """Map an entity deviation to a named event type."""
    direction = "over" if deviation > 0 else "under"
    return _EVENT_TYPE_MAP.get((entity_type, direction), "DEVIATION")


def _causal_rel_type(source_event: str, target_event: str) -> str:
    """Return the causal relationship label for a (source → target) event pair."""
    return _CAUSAL_RELATIONSHIP_MAP.get(
        (source_event, target_event),
        f"{source_event}_INFLUENCES_{target_event}",
    )


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class DeviationEvent:
    """A single forecast-vs-actual deviation event."""
    event_id: str
    timestamp: datetime
    entity_id: str
    entity_type: str
    event_type: str          # classified name, e.g. LATE_DELIVERY
    predicted_value: float
    actual_value: float
    deviation: float         # actual - predicted
    deviation_pct: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalSequence:
    """
    A detected A → B causal sequence.

    source_event: event type of A (e.g. LATE_DELIVERY)
    target_event: event type of B (e.g. INVENTORY_DROP)
    source_entity_id / target_entity_id: the specific entities involved
    occurrence_timestamps: list of (A_time, B_time) pairs
    """
    source_event: str
    target_event: str
    source_entity_id: str
    source_entity_type: str
    target_entity_id: str
    target_entity_type: str
    frequency: int                              # K: how many times this sequence occurred
    source_total: int                           # how many times source event occurred alone
    conditional_probability: float             # P(B|A) = frequency / source_total
    temporal_score: float                       # regularity of the sequence over time
    occurrence_timestamps: list[tuple[datetime, datetime]] = field(default_factory=list)


@dataclass
class TemporalPattern:
    """A validated causal pattern that qualifies for graph evolution."""
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relationship_type: str   # causal label, e.g. LATE_DELIVERY_TRIGGERS_STOCKOUT
    weight: float            # w = α·confidence + β·freq_norm + γ·temporal
    confidence: float        # P(B|A)
    frequency: int           # K occurrences
    temporal_score: float
    support: int = 1         # support: count of occurrences
    probability: float = 0.85 # P(A ∩ B)
    window: int = 30         # observation window in days
    sequence_length: int = 2 # 2, 3, or 4
    path_nodes: list[tuple[str, str]] = field(default_factory=list) # Full (entity_id, entity_type) chain
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiLengthSequence:
    """A detected causal sequence of variable length (length 2, 3, or 4)."""
    sequence_length: int
    events_chain: list[str]
    entities_chain: list[tuple[str, str]]
    frequency: int
    source_total: int
    conditional_probability: float
    temporal_score: float
    occurrence_timestamps: list[list[datetime]] = field(default_factory=list)



# ─── Pattern Detector ─────────────────────────────────────────────────────────

class PatternDetector:
    """
    Detects causal sequential patterns from deviation events.

    Parameters
    ----------
    window_size_days : int
        Sliding window W — only events within this many days are considered.
        Older events are discarded (they may no longer be relevant).

    frequency_threshold : int
        K — minimum number of times a sequence must occur before an edge is added.
        Prevents noise from creating spurious edges.

    confidence_threshold : float
        θ — minimum P(B|A) required.
        If Late Delivery occurred 100 times but Complaint only 20 times,
        P = 0.20 < θ → edge NOT added.

    lag_days : int
        Maximum days between event A and event B for them to count as a sequence.
        Default 7: if B happens within 7 days of A, it's considered caused by A.

    alpha, beta, gamma : float
        Weights for the scoring formula:
        w = α·P(B|A) + β·(freq/max_freq) + γ·temporal_score
    """

    def __init__(
        self,
        window_size_days: int = 90,
        frequency_threshold: int = 3,
        confidence_threshold: float = 0.6,
        lag_days: int = 7,
        alpha: float = 0.4,
        beta: float = 0.35,
        gamma: float = 0.25,
    ):
        self._window_days = window_size_days
        self._K = frequency_threshold           # minimum observations gate
        self._theta = confidence_threshold      # probability gate
        self._lag_days = lag_days
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma

    def detect_patterns(
        self,
        events: list[DeviationEvent],
        reference_time: datetime | None = None,
    ) -> list[TemporalPattern]:
        """
        Main entry: detect all qualifying causal patterns from deviation events.

        Steps:
            1. Filter events to sliding window W
            2. Scan for A → B sequences within lag_days
            3. Count frequencies and compute P(B|A)
            4. Apply K gate and θ gate
            5. Score temporal regularity
            6. Compute final weight and return TemporalPattern list
        """
        if not events:
            return []

        ref_time = reference_time or datetime.now(timezone.utc)
        window_start = ref_time - timedelta(days=self._window_days)

        # Step 1: Filter to sliding window W
        windowed = [e for e in events if e.timestamp >= window_start]
        if len(windowed) < self._K:
            logger.info(
                f"TPKE: only {len(windowed)} events in window "
                f"(need K={self._K}) — no patterns detected"
            )
            return []

        # Sort chronologically — required for sequence scanning
        windowed.sort(key=lambda e: e.timestamp)

        # Step 2: Scan for A → B sequences
        sequences = self._find_sequences(windowed)

        # Step 3–6: Apply gates, score, return patterns
        patterns = self._score_and_filter(sequences)

        logger.info(
            f"TPKE: {len(windowed)} events → "
            f"{len(sequences)} candidate sequences → "
            f"{len(patterns)} patterns above K={self._K}, θ={self._theta}"
        )
        return patterns

    # ── Sequence detection ────────────────────────────────────────────────────

    def _find_sequences(
        self, events: list[DeviationEvent]
    ) -> list[CausalSequence]:
        """
        Scan the sorted event list for A → B sequences.

        For each event A at time T, look forward for any event B
        where B.timestamp is within (T, T + lag_days].

        Count:
        - How many times each (A_type, B_type, A_entity, B_entity) pair occurs
        - How many times each (A_type, A_entity) occurs in total (for P(B|A))
        """
        lag = timedelta(days=self._lag_days)

        # sequence_counts[(src_event, tgt_event, src_id, src_type, tgt_id, tgt_type)]
        sequence_counts: dict[tuple, int] = defaultdict(int)
        sequence_timestamps: dict[tuple, list[tuple[datetime, datetime]]] = defaultdict(list)

        # source_counts[(src_event, src_id, src_type)]
        source_counts: dict[tuple[str, str, str], int] = defaultdict(int)

        n = len(events)
        for i, event_a in enumerate(events):
            src_key = (event_a.event_type, event_a.entity_id, event_a.entity_type)
            source_counts[src_key] += 1

            # Look forward for event B within lag window
            for j in range(i + 1, n):
                event_b = events[j]

                # Stop scanning forward once we exceed lag window
                if event_b.timestamp > event_a.timestamp + lag:
                    break

                # Skip same entity (an entity can't cause itself)
                if event_b.entity_id == event_a.entity_id:
                    continue

                seq_key = (
                    event_a.event_type,
                    event_b.event_type,
                    event_a.entity_id,
                    event_a.entity_type,
                    event_b.entity_id,
                    event_b.entity_type,
                )
                sequence_counts[seq_key] += 1
                sequence_timestamps[seq_key].append(
                    (event_a.timestamp, event_b.timestamp)
                )

        # Build CausalSequence objects
        sequences: list[CausalSequence] = []
        for seq_key, freq in sequence_counts.items():
            src_event, tgt_event, src_id, src_type, tgt_id, tgt_type = seq_key
            src_total = source_counts[(src_event, src_id, src_type)]
            cond_prob = freq / src_total if src_total > 0 else 0.0
            timestamps = sequence_timestamps[seq_key]
            temporal_score = self._compute_temporal_regularity(timestamps)

            sequences.append(CausalSequence(
                source_event=src_event,
                target_event=tgt_event,
                source_entity_id=src_id,
                source_entity_type=src_type,
                target_entity_id=tgt_id,
                target_entity_type=tgt_type,
                frequency=freq,
                source_total=src_total,
                conditional_probability=round(cond_prob, 4),
                temporal_score=round(temporal_score, 4),
                occurrence_timestamps=timestamps,
            ))

        return sequences

    def _find_multi_length_sequences(
        self, events: list[DeviationEvent], max_chain_length: int = 4
    ) -> list[MultiLengthSequence]:
        """
        Scan events for multi-length causal chains:
        Length 2: A → B
        Length 3: A → B → C
        Length 4: A → B → C → D
        """
        lag = timedelta(days=self._lag_days)
        n = len(events)

        chain_counts: dict[tuple, int] = defaultdict(int)
        chain_timestamps: dict[tuple, list[list[datetime]]] = defaultdict(list)
        head_counts: dict[tuple, int] = defaultdict(int)

        for i, event_a in enumerate(events):
            head_key = (event_a.event_type, event_a.entity_id, event_a.entity_type)
            head_counts[head_key] += 1

            for j in range(i + 1, n):
                event_b = events[j]
                if event_b.timestamp > event_a.timestamp + lag:
                    break
                if event_b.entity_id == event_a.entity_id:
                    continue

                # Length 2 chain
                k2 = (
                    (event_a.event_type, event_b.event_type),
                    ((event_a.entity_id, event_a.entity_type), (event_b.entity_id, event_b.entity_type))
                )
                chain_counts[k2] += 1
                chain_timestamps[k2].append([event_a.timestamp, event_b.timestamp])

                if max_chain_length < 3:
                    continue

                # Length 3 chain
                for k in range(j + 1, n):
                    event_c = events[k]
                    if event_c.timestamp > event_b.timestamp + lag:
                        break
                    if event_c.entity_id in (event_a.entity_id, event_b.entity_id):
                        continue

                    k3 = (
                        (event_a.event_type, event_b.event_type, event_c.event_type),
                        ((event_a.entity_id, event_a.entity_type),
                         (event_b.entity_id, event_b.entity_type),
                         (event_c.entity_id, event_c.entity_type))
                    )
                    chain_counts[k3] += 1
                    chain_timestamps[k3].append([event_a.timestamp, event_b.timestamp, event_c.timestamp])

                    if max_chain_length < 4:
                        continue

                    # Length 4 chain
                    for m in range(k + 1, n):
                        event_d = events[m]
                        if event_d.timestamp > event_c.timestamp + lag:
                            break
                        if event_d.entity_id in (event_a.entity_id, event_b.entity_id, event_c.entity_id):
                            continue

                        k4 = (
                            (event_a.event_type, event_b.event_type, event_c.event_type, event_d.event_type),
                            ((event_a.entity_id, event_a.entity_type),
                             (event_b.entity_id, event_b.entity_type),
                             (event_c.entity_id, event_c.entity_type),
                             (event_d.entity_id, event_d.entity_type))
                        )
                        chain_counts[k4] += 1
                        chain_timestamps[k4].append([event_a.timestamp, event_b.timestamp, event_c.timestamp, event_d.timestamp])

        multi_sequences: list[MultiLengthSequence] = []
        for (events_tuple, entities_tuple), freq in chain_counts.items():
            first_event = events_tuple[0]
            first_id, first_type = entities_tuple[0]
            src_total = head_counts[(first_event, first_id, first_type)]
            cond_prob = freq / src_total if src_total > 0 else 0.0
            timestamps = chain_timestamps[(events_tuple, entities_tuple)]
            
            # regularity based on head timestamps
            head_ts = [(ts_list[0], ts_list[-1]) for ts_list in timestamps]
            temp_score = self._compute_temporal_regularity(head_ts)

            multi_sequences.append(MultiLengthSequence(
                sequence_length=len(events_tuple),
                events_chain=list(events_tuple),
                entities_chain=list(entities_tuple),
                frequency=freq,
                source_total=src_total,
                conditional_probability=round(cond_prob, 4),
                temporal_score=round(temp_score, 4),
                occurrence_timestamps=timestamps,
            ))

        return multi_sequences

    # ── Temporal regularity scoring ───────────────────────────────────────────

    def _compute_temporal_regularity(
        self, timestamps: list[tuple[datetime, datetime]]
    ) -> float:
        """
        Score how regularly the sequence recurs over time [0, 1].

        Higher = more evenly distributed (Day 1, Day 5, Day 11, Day 20 → high)
        Lower  = clustered in one burst (Day 1, Day 2, Day 3 → low)

        Uses coefficient of variation of inter-occurrence intervals.
        """
        if len(timestamps) < 2:
            return 0.5

        # Use the A-event timestamps to measure recurrence intervals
        a_times = sorted(t[0] for t in timestamps)
        intervals = [
            (a_times[i] - a_times[i - 1]).total_seconds() / 86400.0
            for i in range(1, len(a_times))
        ]

        if not intervals:
            return 0.5

        mean_interval = float(np.mean(intervals))
        if mean_interval == 0:
            return 1.0

        # Coefficient of variation: lower CV = more regular
        cv = float(np.std(intervals)) / mean_interval

        # Convert to [0, 1]: perfectly regular CV=0 → score=1.0
        regularity = 1.0 / (1.0 + cv)

        # Bonus for spanning a wider time range (not all clustered at start)
        total_span = (a_times[-1] - a_times[0]).total_seconds() / 86400.0
        span_bonus = min(total_span / (self._window_days * 2), 0.2)

        return min(regularity + span_bonus, 1.0)

    # ── Gate application and scoring ──────────────────────────────────────────

    def _score_and_filter(
        self, sequences: list[CausalSequence]
    ) -> list[TemporalPattern]:
        """
        Apply K gate, θ gate, compute weight, return TemporalPattern list.

        K gate:  frequency >= K  (minimum observations)
        θ gate:  P(B|A) >= θ     (conditional probability threshold)
        Weight:  w = α·P(B|A) + β·(freq/max_freq) + γ·temporal_score
        """
        # K gate
        qualified = [s for s in sequences if s.frequency >= self._K]

        # θ gate
        qualified = [s for s in qualified if s.conditional_probability >= self._theta]

        if not qualified:
            return []

        max_freq = max(s.frequency for s in qualified)

        patterns: list[TemporalPattern] = []
        for seq in qualified:
            freq_norm = seq.frequency / max_freq if max_freq > 0 else 0.0

            # w = α·P(B|A) + β·(freq/max_freq) + γ·temporal_score
            weight = (
                self._alpha * seq.conditional_probability
                + self._beta * freq_norm
                + self._gamma * seq.temporal_score
            )
            weight = round(min(weight, 1.0), 4)

            # Determine causal relationship label
            rel_type = _causal_rel_type(seq.source_event, seq.target_event)

            # First and last occurrence timestamps
            a_times = sorted(t[0] for t in seq.occurrence_timestamps)

            patterns.append(TemporalPattern(
                source_id=seq.source_entity_id,
                source_type=seq.source_entity_type,
                target_id=seq.target_entity_id,
                target_type=seq.target_entity_type,
                relationship_type=rel_type,
                weight=weight,
                confidence=seq.conditional_probability,
                frequency=seq.frequency,
                temporal_score=seq.temporal_score,
                evidence={
                    "source_event": seq.source_event,
                    "target_event": seq.target_event,
                    "frequency": seq.frequency,
                    "source_total_occurrences": seq.source_total,
                    "conditional_probability": seq.conditional_probability,
                    "temporal_regularity": seq.temporal_score,
                    "first_seen": a_times[0].isoformat() if a_times else None,
                    "last_seen": a_times[-1].isoformat() if a_times else None,
                    "formula": f"w = {self._alpha}×{seq.conditional_probability} + "
                               f"{self._beta}×{round(freq_norm, 3)} + "
                               f"{self._gamma}×{seq.temporal_score} = {weight}",
                },
            ))

        # Sort by weight descending
        patterns.sort(key=lambda p: p.weight, reverse=True)
        return patterns

    def extract_patterns_from_rca_chains(
        self,
        rca_report: dict[str, Any],
        window_days: int = 30,
    ) -> list[TemporalPattern]:
        """
        Extract TemporalPattern objects from complete RCA causal chains.
        Example: Supplier Delay -> Inventory Shortage -> Customer Complaint
        Calculates support, confidence P(B|A), probability P(A ∩ B), frequency, window.
        """
        report = rca_report.get("report", rca_report)
        causal_chain = report.get("causal_chain", {}).get("events", [])
        contributors = report.get("risk_contributors", [])
        patterns: list[TemporalPattern] = []

        if contributors:
            for c in contributors:
                source_id = str(c.get("entity_id", c.get("node_id", "SUP_001")))
                target_id = str(report.get("target_id", "late_delivery_main"))
                score = float(c.get("score", c.get("contribution_score", 0.75)))
                conf = float(c.get("confidence", 0.85))
                freq = int(c.get("frequency", 5))

                patterns.append(TemporalPattern(
                    source_id=source_id,
                    source_type="Supplier",
                    target_id=target_id,
                    target_type="Shipment",
                    relationship_type="RCA_CAUSAL_CASCADE",
                    weight=round(score, 4),
                    confidence=conf,
                    frequency=freq,
                    temporal_score=0.90,
                    support=freq,
                    probability=round(conf * 0.9, 4),
                    window=window_days,
                    evidence={
                        "rca_type": report.get("rca_type", "late_delivery"),
                        "causal_chain_length": len(causal_chain),
                        "contribution_score": score,
                    },
                ))
        return patterns

    def extract_patterns_from_agent_memory(
        self,
        agent_memory: Any = None,
        limit: int = 50,
    ) -> list[TemporalPattern]:
        """
        Extract TemporalPattern objects directly from Agent Memory prediction history records.
        TPKE uses Agent Memory when learning new graph relationships.
        """
        if agent_memory is None:
            from app.ml.agent_memory import get_agent_memory
            agent_memory = get_agent_memory()

        records = agent_memory.query_records(limit=limit)
        patterns: list[TemporalPattern] = []

        for r in records:
            agent = r.get("agent", "demand")
            prediction = r.get("prediction", 0.0)
            confidence = r.get("confidence", 0.85)
            actual = r.get("actual")
            accuracy = r.get("accuracy", 0.85)

            if accuracy is not None and accuracy < 0.70:
                # Prediction deviation event in Agent Memory -> evolve relationship
                patterns.append(TemporalPattern(
                    source_id=f"{agent.upper()}_AGENT",
                    source_type="MLAgent",
                    target_id="Shipment_W2",
                    target_type="Shipment",
                    relationship_type=f"{agent.upper()}_DEVIATION_LEARNED",
                    weight=round(1.0 - accuracy, 4),
                    confidence=confidence,
                    frequency=1,
                    temporal_score=0.85,
                    support=1,
                    probability=round(confidence * 0.8, 4),
                    window=30,
                    evidence={
                        "agent": agent,
                        "prediction": prediction,
                        "actual": actual,
                        "accuracy": accuracy,
                        "model_version": r.get("model_version", "v1.0.0"),
                    },
                ))
        return patterns

"""
TPKE Engine — Main Orchestrator
=================================
Coordinates the full TPKE pipeline:
    1. Ingest forecast + actual data
    2. Compute deviations → DeviationEvents
    3. Detect temporal patterns (PatternDetector)
    4. Apply edge decay (EdgeManager)
    5. Evolve graph with new patterns (EdgeManager)
    6. Update graph version TPKE mutation count
    7. Return EvolutionReport
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.graph.connection import Neo4jConnectionManager
from app.graph.versioning import GraphVersionManager
from app.tpke.edge_manager import EdgeManager, EdgeMutation, DecayResult
from app.tpke.pattern import PatternDetector, DeviationEvent, TemporalPattern

logger = logging.getLogger(__name__)


@dataclass
class EvolutionReport:
    """Complete report of a TPKE evolution cycle."""
    run_id: str
    timestamp: str
    duration_ms: float
    events_processed: int
    patterns_detected: int
    edges_created: int
    edges_strengthened: int
    edges_decayed: int
    edges_removed: int
    total_tpke_edges: int
    top_patterns: list[dict[str, Any]] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 2),
            "events_processed": self.events_processed,
            "patterns_detected": self.patterns_detected,
            "edges_created": self.edges_created,
            "edges_strengthened": self.edges_strengthened,
            "edges_decayed": self.edges_decayed,
            "edges_removed": self.edges_removed,
            "total_tpke_edges": self.total_tpke_edges,
            "top_patterns": self.top_patterns,
            "parameters": self.parameters,
        }


class TPKEEngine:
    """
    Temporal Pattern-Triggered Knowledge Graph Evolution Engine.

    Inputs:
    - Forecast results (predicted values per entity)
    - Actual uploads (real observed values)

    Output:
    - EvolutionReport with all graph mutations
    """

    def __init__(self, connection: Neo4jConnectionManager, session: AsyncSession):
        self._conn = connection
        self._session = session
        self._settings = get_settings()

        self._detector = PatternDetector(
            window_size_days=self._settings.tpke_window_size_days,
            frequency_threshold=self._settings.tpke_frequency_threshold,
            confidence_threshold=self._settings.tpke_confidence_threshold,
        )
        self._edge_manager = EdgeManager(connection, session)
        self._version_manager = GraphVersionManager(connection, session)

    async def run(
        self,
        forecast_data: list[dict[str, Any]],
        actual_data: list[dict[str, Any]],
        triggered_by: str = "system",
    ) -> EvolutionReport:
        """
        Execute full TPKE evolution cycle.

        Args:
            forecast_data: List of forecast records with keys:
                entity_id, entity_type, predicted_value, forecast_date, metadata
            actual_data: List of actual records with keys:
                entity_id, entity_type, actual_value, date, metadata
            triggered_by: User or system identifier

        Returns:
            EvolutionReport with complete mutation summary
        """
        start = time.perf_counter()
        run_id = f"tpke_{int(time.time())}"
        now = datetime.now(timezone.utc)

        logger.info(f"TPKE run {run_id}: {len(forecast_data)} forecasts, {len(actual_data)} actuals")

        # Step 1: Compute deviation events
        events = self._compute_deviations(forecast_data, actual_data)

        # Step 2: Detect temporal patterns
        patterns = self._detector.detect_patterns(events, reference_time=now)

        # Step 3: Apply edge decay
        decay_result = await self._edge_manager.decay(reference_time=now)

        # Step 4: Evolve graph with detected patterns
        mutations: list[EdgeMutation] = []
        if patterns:
            active_version = await self._version_manager.get_active_version()
            gv_id = active_version["id"] if active_version else None

            mutations = await self._edge_manager.evolve(
                patterns=patterns,
                graph_version_id=gv_id,
                triggered_by=triggered_by,
            )

            # Update TPKE mutation count on graph version
            mutation_count = len(mutations) + len(decay_result.mutations)
            if mutation_count > 0:
                await self._version_manager.increment_tpke_mutations(mutation_count)

        # Step 5: Build report
        total_edges = await self._edge_manager.get_edge_count()
        duration_ms = (time.perf_counter() - start) * 1000

        created = sum(1 for m in mutations if m.action == "edge_created")
        strengthened = sum(1 for m in mutations if m.action == "edge_strengthened")

        report = EvolutionReport(
            run_id=run_id,
            timestamp=now.isoformat(),
            duration_ms=duration_ms,
            events_processed=len(events),
            patterns_detected=len(patterns),
            edges_created=created,
            edges_strengthened=strengthened,
            edges_decayed=decay_result.edges_decayed,
            edges_removed=decay_result.edges_removed,
            total_tpke_edges=total_edges,
            top_patterns=[
                {
                    "source": f"{p.source_type}:{p.source_id}",
                    "target": f"{p.target_type}:{p.target_id}",
                    "relationship": p.relationship_type,
                    "weight": p.weight,
                    "confidence": p.confidence,
                    "frequency": p.frequency,
                }
                for p in patterns[:10]
            ],
            parameters={
                "window_size_days": self._settings.tpke_window_size_days,
                "frequency_threshold": self._settings.tpke_frequency_threshold,
                "confidence_threshold": self._settings.tpke_confidence_threshold,
                "decay_rate": self._settings.tpke_decay_rate,
            },
        )

        logger.info(
            f"TPKE run {run_id} complete: "
            f"{created} created, {strengthened} strengthened, "
            f"{decay_result.edges_decayed} decayed, {decay_result.edges_removed} removed "
            f"({duration_ms:.1f}ms)"
        )

        return report

    async def run_decay_only(self) -> DecayResult:
        """Run only the edge decay pass without new pattern detection."""
        return await self._edge_manager.decay()

    async def get_status(self) -> dict[str, Any]:
        """Get current TPKE engine status."""
        edge_count = await self._edge_manager.get_edge_count()
        active_version = await self._version_manager.get_active_version()
        return {
            "total_tpke_edges": edge_count,
            "active_graph_version": active_version.get("version") if active_version else None,
            "tpke_mutations_on_version": active_version.get("tpke_mutations", 0) if active_version else 0,
            "parameters": {
                "window_size_days": self._settings.tpke_window_size_days,
                "frequency_threshold": self._settings.tpke_frequency_threshold,
                "confidence_threshold": self._settings.tpke_confidence_threshold,
                "decay_rate": self._settings.tpke_decay_rate,
            },
        }

    def _compute_deviations(
        self,
        forecast_data: list[dict[str, Any]],
        actual_data: list[dict[str, Any]],
    ) -> list[DeviationEvent]:
        """
        Match forecast records to actuals and compute deviations.

        Matching key: (entity_id, entity_type, date)
        """
        # Index actuals by (entity_id, entity_type, date_str)
        actual_index: dict[tuple[str, str, str], dict[str, Any]] = {}
        for a in actual_data:
            date_str = self._normalize_date(a.get("date", ""))
            key = (str(a["entity_id"]), str(a["entity_type"]), date_str)
            actual_index[key] = a

        events: list[DeviationEvent] = []
        event_counter = 0

        for f in forecast_data:
            entity_id = str(f["entity_id"])
            entity_type = str(f["entity_type"])
            date_str = self._normalize_date(f.get("forecast_date", ""))
            key = (entity_id, entity_type, date_str)

            actual = actual_index.get(key)
            if not actual:
                continue

            predicted = float(f.get("predicted_value", 0))
            actual_val = float(actual.get("actual_value", 0))
            deviation = actual_val - predicted
            deviation_pct = abs(deviation / predicted) if predicted != 0 else 0.0

            # Only significant deviations become events
            if deviation_pct < 0.1:  # Less than 10% deviation = not interesting
                continue

            try:
                ts = datetime.fromisoformat(date_str) if date_str else datetime.now(timezone.utc)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                ts = datetime.now(timezone.utc)

            event_counter += 1
            events.append(DeviationEvent(
                event_id=f"dev_{event_counter}",
                timestamp=ts,
                entity_id=entity_id,
                entity_type=entity_type,
                predicted_value=predicted,
                actual_value=actual_val,
                deviation=deviation,
                deviation_pct=round(deviation_pct, 4),
                metadata=f.get("metadata", {}),
            ))

        logger.info(f"Computed {len(events)} deviation events from {len(forecast_data)} forecasts")
        return events

    @staticmethod
    def _normalize_date(date_val: Any) -> str:
        """Normalize date to ISO string (date part only)."""
        if not date_val:
            return ""
        s = str(date_val)
        # Take just the date part if it's a datetime
        return s[:10] if len(s) >= 10 else s

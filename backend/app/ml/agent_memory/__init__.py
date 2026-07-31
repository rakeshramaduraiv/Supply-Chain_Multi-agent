"""
AMASCI Agent Memory
=====================
Persistent prediction history for every ML agent.

Stores per-agent records of:
  - prediction value
  - actual value (written back after validation)
  - accuracy  = 1 - |actual - prediction| / max(|actual|, 1)
  - confidence score
  - timestamp
  - top features used
  - whether graph context was used

History is kept in-memory (ring buffer, max 10 000 records per agent)
and appended to a JSONL file for durability across restarts.

Usage
-----
    from app.ml.agent_memory import get_agent_memory

    mem = get_agent_memory()
    rid = mem.record_prediction("demand", prediction=420.0, confidence=0.91,
                                features_used=["holiday", "inventory_stress"])
    mem.record_actual("demand", rid, actual=405.0)
    stats = mem.get_stats("demand")
"""

import json
import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_RECORDS = 10_000
_HISTORY_DIR = Path("data/agent_memory")

AGENTS = ("demand", "supplier", "inventory", "logistics")


@dataclass
class PredictionRecord:
    record_id: str
    agent: str
    prediction: float
    confidence: float
    timestamp: str
    features_used: list[str] = field(default_factory=list)
    graph_context_used: bool = False
    actual: float | None = None
    accuracy: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentMemory:
    """
    Thread-safe ring-buffer prediction history for all four ML agents.

    Each agent maintains its own deque of PredictionRecord objects.
    When an actual value is written back, accuracy is computed and stored.
    """

    def __init__(self, persist: bool = True):
        self._lock = threading.Lock()
        self._history: dict[str, deque[PredictionRecord]] = {
            a: deque(maxlen=_MAX_RECORDS) for a in AGENTS
        }
        self._persist = persist
        if persist:
            _HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    # ── Write ─────────────────────────────────────────────────────────────────

    def record_prediction(
        self,
        agent: str,
        prediction: float,
        confidence: float,
        features_used: list[str] | None = None,
        graph_context_used: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Record a new prediction. Returns the record_id."""
        ts = datetime.now(timezone.utc).isoformat()
        record_id = f"{agent}_{ts}"
        rec = PredictionRecord(
            record_id=record_id,
            agent=agent,
            prediction=prediction,
            confidence=confidence,
            timestamp=ts,
            features_used=features_used or [],
            graph_context_used=graph_context_used,
            metadata=metadata or {},
        )
        with self._lock:
            self._history[agent].append(rec)
        if self._persist:
            self._append_jsonl(agent, rec.to_dict())
        return record_id

    def record_actual(self, agent: str, record_id: str, actual: float) -> bool:
        """
        Write back the actual value for a prediction record.
        Computes accuracy = 1 - |actual - prediction| / max(|actual|, 1).
        """
        with self._lock:
            for rec in self._history[agent]:
                if rec.record_id == record_id:
                    rec.actual = actual
                    rec.accuracy = max(
                        0.0,
                        1.0 - abs(actual - rec.prediction) / max(abs(actual), 1.0),
                    )
                    if self._persist:
                        self._append_jsonl(agent, rec.to_dict())
                    return True
        return False

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_history(self, agent: str, limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent `limit` records for an agent."""
        with self._lock:
            records = list(self._history[agent])
        return [r.to_dict() for r in records[-limit:]]

    def get_stats(self, agent: str) -> dict[str, Any]:
        """
        Return summary statistics for an agent's prediction history.

        Returns:
            total_predictions, predictions_with_actuals,
            mean_accuracy, mean_confidence, recent_accuracy_trend
        """
        with self._lock:
            records = list(self._history[agent])

        if not records:
            return {
                "agent": agent,
                "total_predictions": 0,
                "predictions_with_actuals": 0,
                "mean_accuracy": None,
                "mean_confidence": None,
                "recent_accuracy_trend": [],
            }

        validated = [r for r in records if r.accuracy is not None]
        mean_acc = (
            sum(r.accuracy for r in validated) / len(validated)
            if validated else None
        )
        mean_conf = sum(r.confidence for r in records) / len(records)
        trend = [round(r.accuracy, 4) for r in validated[-20:]]

        return {
            "agent": agent,
            "total_predictions": len(records),
            "predictions_with_actuals": len(validated),
            "mean_accuracy": round(mean_acc, 4) if mean_acc is not None else None,
            "mean_confidence": round(mean_conf, 4),
            "recent_accuracy_trend": trend,
        }

    def get_all_stats(self) -> dict[str, Any]:
        """Return stats for all agents."""
        return {a: self.get_stats(a) for a in AGENTS}

    def get_historical_accuracy(self, agent: str) -> float:
        """
        Return mean accuracy for an agent based on validated predictions.
        Falls back to 0.85 if no validated records exist yet.
        """
        stats = self.get_stats(agent)
        return stats["mean_accuracy"] if stats["mean_accuracy"] is not None else 0.85

    # ── Persistence ───────────────────────────────────────────────────────────

    def _append_jsonl(self, agent: str, record: dict[str, Any]) -> None:
        path = _HISTORY_DIR / f"{agent}_history.jsonl"
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as e:
            logger.warning(f"AgentMemory: could not persist record for {agent}: {e}")


# ── Module-level singleton ────────────────────────────────────────────────────

_agent_memory: AgentMemory | None = None


def get_agent_memory() -> AgentMemory:
    global _agent_memory
    if _agent_memory is None:
        _agent_memory = AgentMemory()
    return _agent_memory

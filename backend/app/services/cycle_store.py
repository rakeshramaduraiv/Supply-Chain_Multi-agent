"""
app/services/cycle_store.py
============================
In-process store for cycle stage events.

Keeps the last N cycles in memory so a client that connects late or drops
can resync via GET /api/v1/cycle/{cycle_id}/stages without needing a DB.
"""

from __future__ import annotations

from collections import deque
from typing import Any

_MAX_CYCLES = 20  # keep last 20 cycles in memory

# cycle_id -> list of stage event dicts (RUNNING + COMPLETED/SKIPPED/FAILED)
_store: dict[str, list[dict[str, Any]]] = {}
_order: deque[str] = deque(maxlen=_MAX_CYCLES)


def record_event(cycle_id: str, event: dict[str, Any]) -> None:
    """Append a stage event dict to the in-memory store."""
    if cycle_id not in _store:
        if len(_order) == _MAX_CYCLES:
            evicted = _order[0]   # deque will drop it on append
            _store.pop(evicted, None)
        _order.append(cycle_id)
        _store[cycle_id] = []
    _store[cycle_id].append(event)


def get_events(cycle_id: str) -> list[dict[str, Any]] | None:
    """Return all recorded events for a cycle, or None if unknown."""
    return _store.get(cycle_id)

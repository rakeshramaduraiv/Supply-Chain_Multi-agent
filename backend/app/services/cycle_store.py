"""
app/services/cycle_store.py
============================
In-process store for cycle events and latest cycle summary.
Keeps the last 20 cycles in memory (no DB dependency).
"""

from collections import OrderedDict
from typing import Any

# ── Event store (last 20 cycles) ─────────────────────────────────────────────

_MAX_CYCLES = 20
_event_store: OrderedDict[str, list[dict]] = OrderedDict()

# ── Latest cycle summary (for footer / GET /cycle/status) ────────────────────

_latest_summary: dict[str, Any] = {}


def record_event(cycle_id: str, event: dict) -> None:
    """Append an event to the store for cycle_id. Evicts oldest if > 20."""
    if cycle_id not in _event_store:
        if len(_event_store) >= _MAX_CYCLES:
            _event_store.popitem(last=False)
        _event_store[cycle_id] = []
    _event_store[cycle_id].append(event)

    # Update summary on cycle.complete events
    if event.get("type") == "cycle.complete":
        global _latest_summary
        _latest_summary = {
            "period":          event.get("period"),
            "cumulative_rows": event.get("cumulative_rows"),
            "last_tpke_run":   event.get("last_tpke_run"),
            "ablation_delta":  event.get("ablation_delta"),
            "last_match_rate": event.get("match_rate"),
        }


def get_events(cycle_id: str) -> list[dict] | None:
    """Return all events for cycle_id, or None if unknown."""
    return _event_store.get(cycle_id)


def get_latest_cycle_summary() -> dict[str, Any]:
    """Return the latest cycle summary dict (empty if no cycle has run)."""
    return _latest_summary


def update_ablation_delta(delta: float) -> None:
    """Patch ablation_delta into the latest summary after an ablation run."""
    _latest_summary["ablation_delta"] = delta

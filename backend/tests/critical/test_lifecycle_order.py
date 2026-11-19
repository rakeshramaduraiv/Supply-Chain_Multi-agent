"""
tests/critical/test_lifecycle_order.py
========================================
Pure state-machine tests for the new step model.
No Neo4j, no DB, no filesystem (tmp_path only).

Regression: step 4 (KG Update) must come BEFORE step 5 (RCA).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


PERIODS = ["2017-10", "2017-11", "2017-12", "2018-01"]


@pytest.fixture()
def state_store(tmp_path, monkeypatch):
    """Patch _state_path and _available_periods to use tmp_path."""
    state_file = tmp_path / "cycle_state.json"

    import app.services.cycle_state_store as store

    monkeypatch.setattr(store, "_state_path", lambda: state_file)
    monkeypatch.setattr(store, "_available_periods", lambda: [
        {"period": p, "filename": f"{p.replace('-','_')}_actual.csv", "rows": 100}
        for p in PERIODS
    ])
    # Also patch cycle_dir to use tmp_path
    monkeypatch.setattr(store, "cycle_dir", lambda period: tmp_path / "cycle" / period)

    return store


def _complete_steps(store, period, steps):
    for s in steps:
        store.record_step(period, s, "COMPLETED", detail={}, duration_ms=1.0)


# ── Test 1: Fresh state ───────────────────────────────────────────────────────

def test_fresh_state(state_store):
    resp = state_store.get_cycle_state_response()
    assert resp["next_expected_period"] == "2017-10"
    entry = next(e for e in resp["available_periods"] if e["period"] == "2017-10")
    assert entry["ui_step"] == 1


# ── Test 2: Cannot run step 2 before step 1 ──────────────────────────────────

def test_require_step_blocks_out_of_order(state_store):
    with pytest.raises(RuntimeError, match="finish step 1"):
        state_store.require_step("2017-10", 2)


# ── Test 3: RCA (step 5) blocked until KG Update (step 4) done ───────────────

def test_rca_blocked_until_kg_update(state_store):
    """Core regression: step 5 (RCA) must not run before step 4 (KG Update)."""
    _complete_steps(state_store, "2017-10", [1, 2, 3])
    with pytest.raises(RuntimeError, match="Knowledge Graph Update"):
        state_store.require_step("2017-10", 5)


# ── Test 4: TPKE (step 6) blocked until RCA (step 5) done ────────────────────

def test_tpke_blocked_until_rca(state_store):
    _complete_steps(state_store, "2017-10", [1, 2, 3, 4])
    with pytest.raises(RuntimeError, match="Root Cause Analysis"):
        state_store.require_step("2017-10", 6)


# ── Test 5: ui_step == 8 after steps 1-7, period still open ──────────────────

def test_ui_step_8_before_close(state_store):
    _complete_steps(state_store, "2017-10", list(range(1, 8)))
    resp = state_store.get_cycle_state_response()
    entry = next(e for e in resp["available_periods"] if e["period"] == "2017-10")
    assert entry["ui_step"] == 8
    # next_expected_period is still 2017-10 (not closed yet)
    assert resp["next_expected_period"] == "2017-10"


# ── Test 6: close_period before step 7 done → raises ─────────────────────────

def test_close_period_requires_all_steps(state_store):
    _complete_steps(state_store, "2017-10", list(range(1, 7)))  # missing step 7
    with pytest.raises(RuntimeError, match="finish steps 1-7"):
        state_store.close_period("2017-10")


# ── Test 7: close_period advances next_expected_period ───────────────────────

def test_close_period_advances_next(state_store):
    _complete_steps(state_store, "2017-10", list(range(1, 8)))
    state_store.close_period("2017-10")
    resp = state_store.get_cycle_state_response()
    assert resp["next_expected_period"] == "2017-11"
    entry = next(e for e in resp["available_periods"] if e["period"] == "2017-11")
    assert entry["ui_step"] == 1


# ── Test 8: Loop all four months → all_complete ───────────────────────────────

def test_all_four_months_complete(state_store):
    for period in PERIODS:
        _complete_steps(state_store, period, list(range(1, 8)))
        state_store.close_period(period)
    resp = state_store.get_cycle_state_response()
    assert resp["all_complete"] is True
    assert resp["next_expected_period"] is None


# ── Test 9: Re-running a COMPLETED step raises ────────────────────────────────

def test_rerun_completed_step_raises(state_store):
    _complete_steps(state_store, "2017-10", [1])
    with pytest.raises(RuntimeError, match="already completed"):
        state_store.require_step("2017-10", 1)


# ── Test 10: Re-running a FAILED step is allowed ─────────────────────────────

def test_rerun_failed_step_allowed(state_store):
    state_store.record_step("2017-10", 1, "FAILED", error="boom")
    # Should not raise — FAILED step can be retried
    ps = state_store.require_step("2017-10", 1)
    assert ps is not None

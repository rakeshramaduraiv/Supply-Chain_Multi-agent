"""
AMASCI End-to-End Walkthrough Script
Tests the complete 8-step lifecycle across all 4 holdout periods:
2017-10, 2017-11, 2017-12, and 2018-01.
Verifies all mathematical outputs, holdout row counts, and agent models.
"""

import sys
import json
import httpx
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
PERIODS = [
    ("2017-10", "2017_10_actual.csv", 2255),
    ("2017-11", "2017_11_actual.csv", 2055),
    ("2017-12", "2017_12_actual.csv", 2124),
    ("2018-01", "2018_01_actual.csv", 2123),
]

ACTUALS_DIR = Path("data/actuals_real")


def run():
    client = httpx.Client(base_url=BASE_URL, timeout=120.0)

    print("=== AMASCI Phase 1 Walkthrough ===")
    
    # 0. Health & Reset
    health = client.get("/health").json()
    print(f"[0] System health: {health.get('status')} | Version: {health.get('version')}")
    
    reset_res = client.post("/cycle/reset?confirm=true")
    assert reset_res.status_code == 200, f"Reset failed: {reset_res.text}"
    print("[0] Cycle state reset confirmed.")

    state = client.get("/cycle/state").json()
    assert state.get("next_expected_period") == "2017-10"
    assert len(state.get("available_periods", [])) == 4
    print(f"[0] Initial state OK: next={state.get('next_expected_period')}, periods={len(state['available_periods'])}")

    # Check Dataset endpoints
    ds_sum = client.get("/dataset/summary").json()
    print(f"[0] Dataset summary keys: {list(ds_sum.keys())}")

    # Walk through each period
    for idx, (period, csv_name, expected_rows) in enumerate(PERIODS, 1):
        print(f"\n==========================================")
        print(f"--> HOLD-OUT PERIOD {idx}/4: {period}")
        print(f"==========================================")

        # Step 1: Generate Forecast
        print(f"[{period} Step 1] Generating multi-agent forecast...")
        r1 = client.post(f"/cycle/{period}/forecast")
        assert r1.status_code == 200, f"Step 1 failed: {r1.text}"
        d1 = r1.json()["detail"]
        print(f"    Step 1 Completed: target={d1.get('target_period')}, categories={d1.get('categories')}")

        # Step 2: Upload Actuals CSV
        csv_path = ACTUALS_DIR / csv_name
        assert csv_path.exists(), f"Actuals CSV not found: {csv_path}"
        print(f"[{period} Step 2] Uploading actuals: {csv_name} ({csv_path.stat().st_size:,} bytes)...")
        with open(csv_path, "rb") as f:
            files = {"file": (csv_name, f, "text/csv")}
            r2 = client.post(f"/cycle/{period}/actuals", files=files)
        assert r2.status_code == 200, f"Step 2 failed: {r2.text}"
        d2 = r2.json()["detail"]
        print(f"    Step 2 Completed: rows={d2.get('rows')} (expected={expected_rows}), date_range={d2.get('date_min')} to {d2.get('date_max')}")
        assert d2.get("rows") == expected_rows, f"Row count mismatch: got {d2.get('rows')}, expected {expected_rows}"

        # Step 3: Evaluate Actual vs Predicted
        print(f"[{period} Step 3] Evaluating actuals vs forecast...")
        r3 = client.post(f"/cycle/{period}/evaluate")
        assert r3.status_code == 200, f"Step 3 failed: {r3.text}"
        d3 = r3.json()["detail"]
        mape = d3.get("demand_mape")
        match_rate = d3.get("match_rate")
        print(f"    Step 3 Completed: MAPE={mape:.2f}%, Match Rate={match_rate:.2%}, Matched Keys={d3.get('matched_keys')}/{d3.get('forecast_keys')}")
        assert mape is not None and not (mape != mape), "MAPE is NaN!"

        # Step 4: Knowledge Graph Update
        print(f"[{period} Step 4] Updating Knowledge Graph observations...")
        r4 = client.post(f"/cycle/{period}/graph-update")
        assert r4.status_code == 200, f"Step 4 failed: {r4.text}"
        d4 = r4.json()["detail"]
        print(f"    Step 4 Completed: observations={d4.get('observations_written')}, nodes_matched={d4.get('nodes_matched')}, graph_version={d4.get('graph_version')}")
        assert d4.get("observations_written", 0) > 0, "No observations written!"

        # Step 5: Root Cause Analysis
        print(f"[{period} Step 5] Running Root Cause Analysis...")
        r5 = client.post(f"/cycle/{period}/rca")
        assert r5.status_code == 200, f"Step 5 failed: {r5.text}"
        d5 = r5.json()["detail"]
        print(f"    Step 5 Completed: target={d5.get('target_id')}, type={d5.get('rca_type')}, top_causes={len(d5.get('top_causes', []))}")

        # Step 6: TPKE Evolution
        print(f"[{period} Step 6] Running Temporal Pattern KG Evolution (TPKE)...")
        r6 = client.post(f"/cycle/{period}/tpke")
        assert r6.status_code == 200, f"Step 6 failed: {r6.text}"
        d6 = r6.json()["detail"]
        print(f"    Step 6 Completed: edges_created={d6.get('edges_created')}, edges_strengthened={d6.get('edges_strengthened')}, version={d6.get('tpke_version')}")

        # Step 7: Learn & Agent Scores
        print(f"[{period} Step 7] Retraining models and evaluating agent scores...")
        r7 = client.post(f"/cycle/{period}/learn")
        assert r7.status_code == 200, f"Step 7 failed: {r7.text}"
        d7 = r7.json()["detail"]
        agents = d7.get("agents", {})
        print(f"    Step 7 Completed: cumulative_rows={d7.get('cumulative_rows'):,}, trained_through={d7.get('trained_through')}")
        print(f"    Active Agents: {list(agents.keys())}")
        assert "inventory" not in agents, "Inventory agent must be formally excluded!"
        for ag in ("demand", "supplier", "logistics"):
            assert ag in agents, f"Missing required agent: {ag}"

        # Step 8: Close Period
        print(f"[{period} Step 8] Closing period {period}...")
        r8 = client.post(f"/cycle/{period}/close")
        assert r8.status_code == 200, f"Step 8 failed: {r8.text}"
        d8 = r8.json()
        print(f"    Step 8 Completed: closed={d8.get('closed')}, next_period={d8.get('next_period')}")

    # Verify Terminal State
    print("\n==========================================")
    print("--> VERIFYING FINAL TERMINAL CYCLE STATE")
    print("==========================================")
    final_state = client.get("/cycle/state").json()
    print(f"All complete: {final_state.get('all_complete')}")
    print(f"Total processed: {final_state.get('total_complete')}/{final_state.get('total_available')}")
    print(f"Next expected: {final_state.get('next_expected_period')}")
    assert final_state.get("all_complete") is True
    assert final_state.get("total_complete") == 4
    assert final_state.get("next_expected_period") is None
    print("\nSUCCESS: All 4 holdout periods walked cleanly through all 8 lifecycle steps!")


if __name__ == "__main__":
    run()

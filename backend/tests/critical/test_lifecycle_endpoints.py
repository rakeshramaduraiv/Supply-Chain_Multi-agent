"""
tests/critical/test_lifecycle_endpoints.py
============================================
Tests for step endpoints and lifecycle integrity (Part 3.2).
Uses FastAPI TestClient with mocked Neo4j / TPKE / training.
"""

from __future__ import annotations

import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.cycle_routes import router as cycle_router
import app.services.cycle_state_store as state_store


PERIODS = ["2017-10", "2017-11", "2017-12", "2018-01"]


@pytest.fixture()
def client_and_store(tmp_path, monkeypatch):
    """Set up TestClient and patch cycle state paths to tmp_path."""
    state_file = tmp_path / "cycle_state.json"
    cycle_dir_path = tmp_path / "cycle"

    monkeypatch.setattr(state_store, "_state_path", lambda: state_file)
    monkeypatch.setattr(state_store, "cycle_dir", lambda p: cycle_dir_path / p)
    monkeypatch.setattr(state_store, "_available_periods", lambda: [
        {"period": p, "filename": f"{p.replace('-','_')}_actual.csv", "rows": 100}
        for p in PERIODS
    ])

    app = FastAPI()
    app.include_router(cycle_router)
    client = TestClient(app)
    return client, state_store, cycle_dir_path


def test_advance_returns_410(client_and_store):
    client, _, _ = client_and_store
    resp = client.post("/cycle/advance/2017-10")
    assert resp.status_code == 410


def test_rca_before_graph_update_returns_409(client_and_store):
    """POST /cycle/2017-10/rca right after evaluate (step 3) -> 409."""
    client, store, _ = client_and_store
    # Complete steps 1, 2, 3
    store.record_step("2017-10", 1, "COMPLETED")
    store.record_step("2017-10", 2, "COMPLETED")
    store.record_step("2017-10", 3, "COMPLETED")

    resp = client.post("/cycle/2017-10/rca")
    assert resp.status_code == 409
    assert "Knowledge Graph Update" in resp.json()["detail"]


@pytest.mark.anyio
async def test_graph_update_batch_size_equals_all_rows(tmp_path):
    """/graph-update builds its batch from all rows, not <= 200."""
    from app.graph.actual_integration import ActualIntegrationLayer

    # Create dummy actuals dataframe with 3 categories, 2 departments, 4 routes
    records = []
    for cat in ["CatA", "CatB", "CatC"]:
        for dept in ["Dept1", "Dept2"]:
            for mode in ["Standard", "Express"]:
                for reg in ["East", "West"]:
                    records.append({
                        "Category Name": cat,
                        "Department Name": dept,
                        "Shipping Mode": mode,
                        "Order Region": reg,
                        "Order Item Quantity": 5,
                        "Late_delivery_risk": 0,
                        "shipping_delay_days": 1.0,
                    })
    df = pd.DataFrame(records)

    mock_conn = MagicMock()
    mock_conn.execute_write = AsyncMock(side_effect=[
        [{"nodes_matched": 10}],
        [{"version": 1}],
    ])

    layer = ActualIntegrationLayer(connection=mock_conn)
    result = await layer.sync_actuals_scoped(df, period="2017-10")

    # Categories = 3, Departments = 2, Routes = 4 -> Total distinct entities in batch = 9
    assert result["observations_written"] == 3 + 2 + 4
    assert mock_conn.execute_write.called
    written_batch = mock_conn.execute_write.call_args_list[0][0][1]["batch"]
    assert len(written_batch) == 9


@pytest.mark.anyio
async def test_sync_rca_and_actuals_empty_zero_observations():
    """sync_rca with no contributors writes 0; auto_sync_actuals(None) writes 0."""
    from app.graph.rca_integration import RCAIntegrationLayer, auto_sync_rca
    from app.graph.actual_integration import ActualIntegrationLayer, auto_sync_actuals

    mock_conn = MagicMock()
    mock_conn.execute_write = AsyncMock(return_value=[{"updated": 0}])

    rca_layer = RCAIntegrationLayer(connection=mock_conn)
    res_rca = await rca_layer.sync_rca({"risk_contributors": []})
    assert res_rca["updated_relationships"] == 0
    assert not mock_conn.execute_write.called

    res_auto_rca = await auto_sync_rca(None)
    assert res_auto_rca["updated_relationships"] == 0

    actual_res = await auto_sync_actuals(None)
    assert actual_res["updated"] == 0
    assert actual_res["reason"] == "no actuals"


def test_tpke_run_uses_rca_json(client_and_store, monkeypatch):
    """TPKEEngine.run is called with rca_report equal to rca.json."""
    client, store, cycle_dir_path = client_and_store

    p = "2017-10"
    for s in range(1, 6):
        store.record_step(p, s, "COMPLETED")

    p_dir = cycle_dir_path / p
    p_dir.mkdir(parents=True, exist_ok=True)
    (p_dir / "forecast.json").write_text(json.dumps({"category_forecasts": []}))
    (p_dir / "evaluation.json").write_text(json.dumps({"comparison_records": []}))
    rca_content = {"report": {"target_id": "CatA", "risk_contributors": []}}
    (p_dir / "rca.json").write_text(json.dumps(rca_content))

    mock_report = MagicMock()
    mock_report.edges_created = 2
    mock_report.edges_strengthened = 3
    mock_report.edges_decayed = 0
    mock_report.run_id = "tpke_v1"

    mock_engine = MagicMock()
    mock_engine.run = AsyncMock(return_value=mock_report)

    with patch("app.tpke.engine.TPKEEngine", return_value=mock_engine), \
         patch("app.graph.connection.get_connection_manager", return_value=MagicMock()), \
         patch("app.database.postgres.async_session_factory") as mock_sf:
        mock_ctx = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

        resp = client.post(f"/cycle/{p}/tpke")
        assert resp.status_code == 200
        assert mock_engine.run.called
        call_kwargs = mock_engine.run.call_args.kwargs
        assert call_kwargs["rca_report"] == rca_content["report"]


def test_learn_idempotent_appends_once(client_and_store, monkeypatch):
    """POST /cycle/{p}/learn twice appends to cumulative store exactly once."""
    client, store, cycle_dir_path = client_and_store

    p = "2017-10"
    for s in range(1, 7):
        store.record_step(p, s, "COMPLETED")

    p_dir = cycle_dir_path / p
    p_dir.mkdir(parents=True, exist_ok=True)
    df_actual = pd.DataFrame([{"Category Name": "CatA", "Order Item Quantity": 1}])
    df_actual.to_parquet(p_dir / "actuals.parquet", index=False)
    (p_dir / "evaluation.json").write_text(json.dumps({"demand_mape": 4.5}))

    mock_store = MagicMock()
    mock_store.load_full.return_value = df_actual
    mock_store.periods.return_value = []
    mock_report = MagicMock()
    mock_report.cumulative_rows = 100
    mock_store.append.return_value = mock_report

    mock_orch = MagicMock()
    mock_orch.train_all.return_value = {"demand": MagicMock()}

    with patch("app.store.cumulative.CumulativeStore", return_value=mock_store), \
         patch("app.feature_engineering.engineer_features_on_test", return_value=df_actual), \
         patch("app.ml.training.TrainingOrchestrator", return_value=mock_orch), \
         patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.retrain_on_upload = True

        resp1 = client.post(f"/cycle/{p}/learn")
        assert resp1.status_code == 200
        assert mock_store.append.call_count == 1
        assert mock_orch.train_all.call_count == 1

        # Simulate retry after a forced failure, when period is now in store.periods()
        store.record_step(p, 7, "FAILED")
        mock_store.periods.return_value = [p]
        resp2 = client.post(f"/cycle/{p}/learn")
        assert resp2.status_code == 200
        # append count must NOT have increased!
        assert mock_store.append.call_count == 1


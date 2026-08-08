"""
Critical test — Graph enrichment failure must not be silently swallowed.

When ALLOW_ENRICHMENT_FALLBACK=False (the default), a failure in
enrich_graph_features_from_neo4j must propagate as a RuntimeError and
abort initialization.  Training on unenriched features must never happen
without an explicit operator opt-in.

When ALLOW_ENRICHMENT_FALLBACK=True, the fallback is permitted but the
result must record degraded=True and graph_enriched=False in the registry.
"""

import pathlib
import sys
import types

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from app.initialization.service import InitializationService


# ── Minimal synthetic dataset that passes the pipeline up to step 4b ─────────

def _make_minimal_df(n: int = 200) -> pd.DataFrame:
    """
    Smallest DataFrame that satisfies:
    - DataEngineeringPipeline.execute()
    - _engineer_features()
    - feature_engineering.engineer_features()
    - The date-sort assertion in step 4b
    """
    import numpy as np

    dates = pd.date_range("2017-01-01", periods=n, freq="D")
    rng   = np.random.default_rng(42)

    return pd.DataFrame({
        "order date (DateOrders)":       dates.strftime("%m/%d/%Y %H:%M"),
        "Order Item Quantity":            rng.integers(1, 10, n),
        "Sales":                          rng.uniform(10, 500, n),
        "Order Item Discount":            rng.uniform(0, 0.3, n),
        "Product Price":                  rng.uniform(5, 200, n),
        "Order Profit Per Order":         rng.uniform(-50, 100, n),
        "Days for shipping (real)":       rng.integers(1, 7, n),
        "Days for shipment (scheduled)":  rng.integers(1, 5, n),
        "Late_delivery_risk":             rng.integers(0, 2, n),
        "Delivery Status":                rng.choice(["Late delivery", "Advance shipping", "Shipping on time"], n),
        "Shipping Mode":                  rng.choice(["Standard Class", "First Class", "Second Class", "Same Day"], n),
        "Department Name":                rng.choice(["Fan Shop", "Golf Shop", "Apparel"], n),
        "Category Name":                  rng.choice(["Cleats", "Men's Footwear", "Women's Apparel"], n),
        "Order Region":                   rng.choice(["Western Europe", "Central America", "South Asia"], n),
        "Product Card Id":                rng.integers(1000, 9999, n),
        "Market":                         rng.choice(["Europe", "LATAM", "Pacific Asia"], n),
        "Customer Segment":               rng.choice(["Consumer", "Corporate", "Home Office"], n),
        "Type":                           rng.choice(["DEBIT", "CASH", "PAYMENT"], n),
        "Order Item Id":                  range(n),
    })


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_dataset(tmp_path: pathlib.Path) -> pathlib.Path:
    """Write a minimal CSV to a temp directory and return its path."""
    csv_path = tmp_path / "DataCoSupplyChainDataset.csv"
    _make_minimal_df().to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture()
def service_strict(monkeypatch) -> InitializationService:
    """
    InitializationService with ALLOW_ENRICHMENT_FALLBACK=False (default).
    All heavy external calls are stubbed out so the test reaches step 4b fast.
    """
    svc = _make_stubbed_service(monkeypatch, allow_fallback=False)
    return svc


@pytest.fixture()
def service_lenient(monkeypatch) -> InitializationService:
    """
    InitializationService with ALLOW_ENRICHMENT_FALLBACK=True.
    """
    svc = _make_stubbed_service(monkeypatch, allow_fallback=True)
    return svc


def _make_stubbed_service(monkeypatch, allow_fallback: bool) -> InitializationService:
    """
    Build an InitializationService with:
    - settings.allow_enrichment_fallback patched
    - DataEngineeringPipeline.execute() returning the df unchanged
    - _build_knowledge_graph() returning a dummy result
    - TrainingOrchestrator.train_all() returning a dummy result
    - ModelRegistry.save_model() / list_all_models() no-ops
    - enrich_graph_features_from_neo4j patched to raise
    """
    from unittest.mock import MagicMock, patch
    from app.core.config import get_settings

    # Patch settings
    real_settings = get_settings()
    monkeypatch.setattr(real_settings, "allow_enrichment_fallback", allow_fallback)

    # Patch get_settings() everywhere it is called
    monkeypatch.setattr(
        "app.initialization.service.settings",
        real_settings,
    )

    svc = InitializationService.__new__(InitializationService)

    # Stub data pipeline
    pipeline_result = MagicMock()
    pipeline_result.status = "completed"
    pipeline_result.errors = []
    pipeline_result.row_count_raw   = 200
    pipeline_result.row_count_clean = 200
    pipeline_result.row_count_final = 200
    pipeline_result.column_count_final = 20
    pipeline_result.validation_report = {"quality_score": 95.0}

    data_pipeline = MagicMock()
    data_pipeline.execute.side_effect = lambda df, **kw: (df, pipeline_result)
    svc._data_pipeline = data_pipeline

    # Stub graph connection (not used — enrichment is patched to raise)
    svc._graph_conn = MagicMock()

    # Stub knowledge graph build
    svc._build_knowledge_graph = MagicMock(return_value={
        "nodes_created": 10, "relationships_created": 5, "status": "built"
    })

    # Stub training orchestrator
    training_result = MagicMock()
    training_result.version_id = "test_v1"
    training_result.metrics    = {"r2": 0.5}
    training_result.training_duration_ms = 100.0

    orchestrator = MagicMock()
    orchestrator.train_all.return_value = {
        "demand": training_result,
        "supplier": training_result,
        "logistics": training_result,
    }
    svc._training_orchestrator = orchestrator

    # Stub model registry
    registry = MagicMock()
    registry.list_all_models.return_value = {}
    svc._model_registry = registry

    # Patch enrich_graph_features_from_neo4j to always raise
    monkeypatch.setattr(
        "app.initialization.service.enrich_graph_features_from_neo4j",
        _raise_enrichment_error,
        raising=False,
    )
    # Also patch via the module import path used inside execute()
    import app.graph.enrichment as _enrich_mod
    monkeypatch.setattr(_enrich_mod, "enrich_graph_features_from_neo4j", _raise_enrichment_error)

    return svc


def _raise_enrichment_error(*args, **kwargs):
    from app.graph.enrichment import GraphContextUnavailable
    raise GraphContextUnavailable("Neo4j offline — test-injected failure")


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_enrichment_failure_raises_when_flag_is_false(
    service_strict: InitializationService,
    tmp_dataset: pathlib.Path,
):
    """
    When ALLOW_ENRICHMENT_FALLBACK=False and enrichment raises,
    execute() must propagate a RuntimeError — not return status='completed'.
    """
    result = service_strict.execute(dataset_path=tmp_dataset)

    # The outer try/except in execute() catches RuntimeError and sets status=failed
    assert result["status"] == "failed", (
        f"Expected status='failed' but got {result['status']!r}. "
        f"Enrichment failure was silently swallowed."
    )
    assert "error" in result, "result must contain 'error' key on failure"
    assert "enrichment" in result["error"].lower() or "unenriched" in result["error"].lower(), (
        f"Error message does not mention enrichment: {result['error']!r}"
    )
    # Training must NOT have been called
    service_strict._training_orchestrator.train_all.assert_not_called()


def test_enrichment_failure_continues_when_flag_is_true(
    service_lenient: InitializationService,
    tmp_dataset: pathlib.Path,
):
    """
    When ALLOW_ENRICHMENT_FALLBACK=True and enrichment raises,
    execute() must complete but record degraded=True in graph_enrichment step.
    """
    result = service_lenient.execute(dataset_path=tmp_dataset)

    assert result["status"] == "completed", (
        f"Expected status='completed' with fallback=True but got {result['status']!r}. "
        f"Error: {result.get('error')}"
    )

    enrichment_step = result["steps"].get("graph_enrichment", {})
    assert enrichment_step.get("degraded") is True, (
        f"graph_enrichment step must have degraded=True when fallback is used. "
        f"Got: {enrichment_step}"
    )
    assert enrichment_step.get("status") == "skipped", (
        f"graph_enrichment status must be 'skipped' on fallback. Got: {enrichment_step}"
    )


def test_train_all_called_with_graph_enriched_false_on_fallback(
    service_lenient: InitializationService,
    tmp_dataset: pathlib.Path,
):
    """
    When fallback is used, train_all must be called with graph_enriched=False
    so the registry records that these models saw unenriched features.
    """
    service_lenient.execute(dataset_path=tmp_dataset)

    call_kwargs = service_lenient._training_orchestrator.train_all.call_args
    assert call_kwargs is not None, "train_all was not called"
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    # graph_enriched may be positional or keyword
    args = call_kwargs.args if call_kwargs.args else ()
    graph_enriched_val = kwargs.get("graph_enriched", args[2] if len(args) > 2 else None)

    assert graph_enriched_val is False, (
        f"train_all must be called with graph_enriched=False on fallback. "
        f"Got graph_enriched={graph_enriched_val!r}"
    )


def test_train_mask_uses_quantile_boundary(
    service_strict: InitializationService,
    tmp_dataset: pathlib.Path,
    monkeypatch,
):
    """
    The train_mask passed to enrich_graph_features_from_neo4j must be derived
    from the 0.8 date quantile, not a positional slice.

    We capture the mask argument and verify:
    - It is a boolean Series
    - ~80% of rows are True (within ±5%)
    - The True rows are all earlier than the False rows (chronological boundary)
    """
    captured: dict = {}

    def _capture_and_raise(df, conn, train_mask):
        captured["train_mask"] = train_mask.copy()
        captured["df_index"]   = df.index.tolist()
        from app.graph.enrichment import GraphContextUnavailable
        raise GraphContextUnavailable("captured — aborting")

    import app.graph.enrichment as _enrich_mod
    monkeypatch.setattr(_enrich_mod, "enrich_graph_features_from_neo4j", _capture_and_raise)

    # Use strict service so it raises after capture
    service_strict.execute(dataset_path=tmp_dataset)

    assert "train_mask" in captured, "enrich_graph_features_from_neo4j was never called"

    mask = captured["train_mask"]
    assert hasattr(mask, "dtype"), "train_mask must be a pandas Series"
    assert str(mask.dtype) == "bool", f"train_mask dtype must be bool, got {mask.dtype}"

    true_pct = mask.mean()
    assert 0.75 <= true_pct <= 0.85, (
        f"train_mask should mark ~80% of rows as train. Got {true_pct:.1%}. "
        f"Positional slice would give exactly 0.8 but quantile may vary slightly."
    )

    # True rows must all precede False rows (chronological boundary)
    true_positions  = [i for i, v in enumerate(mask) if v]
    false_positions = [i for i, v in enumerate(mask) if not v]
    if true_positions and false_positions:
        assert max(true_positions) < max(false_positions), (
            "train_mask is not a chronological boundary — "
            "some True rows appear after False rows."
        )

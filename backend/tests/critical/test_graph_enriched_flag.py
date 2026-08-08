"""
tests/critical/test_graph_enriched_flag.py
============================================
Verifies that graph_enriched is an explicit opt-in that defaults to False.

Two scenarios:
  1. Enrichment raises GraphContextUnavailable + ALLOW_ENRICHMENT_FALLBACK=True
     → every registry entry written must have graph_enriched == False
  2. Enrichment succeeds (monkeypatched to return df unchanged)
     → every registry entry written must have graph_enriched == True

These tests use a tiny synthetic DataFrame so they run in < 5 s without Neo4j.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.graph.enrichment import GraphContextUnavailable
from app.ml.registry import ModelRegistry, ModelVersion
from app.ml.training import TrainingOrchestrator


# ── Minimal synthetic dataset ─────────────────────────────────────────────────

def _make_df(n: int = 600) -> pd.DataFrame:
    """Smallest DataFrame that passes feature engineering without errors."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2016-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "order date (DateOrders)":      dates,
        "Order Item Quantity":          rng.integers(1, 10, n).astype(float),
        "Sales":                        rng.uniform(10, 500, n),
        "Order Profit Per Order":       rng.uniform(-50, 200, n),
        "Order Item Discount":          rng.uniform(0, 0.4, n),
        "Product Price":                rng.uniform(5, 300, n),
        "Days for shipping (real)":     rng.integers(1, 7, n).astype(float),
        "Days for shipment (scheduled)":rng.integers(1, 5, n).astype(float),
        "Late_delivery_risk":           rng.integers(0, 2, n).astype(float),
        "Department Name":              rng.choice(["Fan Shop", "Golf Shop", "Apparel"], n),
        "Shipping Mode":                rng.choice(["Standard Class", "First Class"], n),
        "Order Region":                 rng.choice(["Western Europe", "Central America"], n),
        "Customer Segment":             rng.choice(["Consumer", "Corporate"], n),
        "Market":                       rng.choice(["Europe", "LATAM"], n),
        # Graph context features — Tier-1 pandas aggregates (will be overwritten by enrichment)
        "graph_supplier_reliability":   rng.uniform(0.5, 1.0, n),
        "graph_inventory_stress":       rng.uniform(0.0, 0.5, n),
        "graph_avg_shipping_delay":     rng.uniform(0.5, 3.0, n),
        "graph_has_upcoming_event":     rng.integers(0, 2, n).astype(float),
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _registry_entries(registry_path: Path) -> dict[str, bool]:
    """Return {intelligence_type: graph_enriched} for the latest version of each."""
    data = json.loads(registry_path.read_text())
    return {k: versions[-1]["graph_enriched"] for k, versions in data.items() if versions}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestGraphEnrichedFlagFalseOnFallback:
    """When enrichment fails and fallback is allowed, flag must be False."""

    def test_flag_is_false_when_enrichment_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ALLOW_ENRICHMENT_FALLBACK", "true")

        def _failing_enrich(df, conn, train_mask):
            raise GraphContextUnavailable("Neo4j offline — test sentinel")

        with patch(
            "app.graph.enrichment.enrich_graph_features_from_neo4j",
            side_effect=_failing_enrich,
        ):
            registry = ModelRegistry(base_dir=tmp_path)
            orchestrator = TrainingOrchestrator(registry=registry)
            df = _make_df()

            # graph_enriched=False must be forwarded explicitly
            orchestrator.train_all(df, dataset_version="test_v1", graph_enriched=False)

        entries = _registry_entries(tmp_path / "registry.json")
        assert entries, "Registry must not be empty after train_all"
        for agent, flag in entries.items():
            assert flag is False, (
                f"agent={agent}: graph_enriched should be False when enrichment "
                f"failed, got {flag!r}"
            )

    def test_default_is_false_without_explicit_kwarg(self, tmp_path):
        """train_all() with no graph_enriched kwarg must default to False."""
        registry = ModelRegistry(base_dir=tmp_path)
        orchestrator = TrainingOrchestrator(registry=registry)
        df = _make_df()

        orchestrator.train_all(df, dataset_version="test_default")

        entries = _registry_entries(tmp_path / "registry.json")
        for agent, flag in entries.items():
            assert flag is False, (
                f"agent={agent}: default graph_enriched must be False, got {flag!r}"
            )


class TestGraphEnrichedFlagTrueOnSuccess:
    """When enrichment succeeds, flag must be True."""

    def test_flag_is_true_when_enrichment_succeeds(self, tmp_path):
        def _noop_enrich(df, conn, train_mask):
            # Enrichment succeeds — returns df unchanged (values already present)
            return df.copy()

        with patch(
            "app.graph.enrichment.enrich_graph_features_from_neo4j",
            side_effect=_noop_enrich,
        ):
            registry = ModelRegistry(base_dir=tmp_path)
            orchestrator = TrainingOrchestrator(registry=registry)
            df = _make_df()

            orchestrator.train_all(df, dataset_version="test_enriched", graph_enriched=True)

        entries = _registry_entries(tmp_path / "registry.json")
        assert entries, "Registry must not be empty after train_all"
        for agent, flag in entries.items():
            assert flag is True, (
                f"agent={agent}: graph_enriched should be True when enrichment "
                f"succeeded, got {flag!r}"
            )


class TestRegistryPruning:
    """Registry must keep at most 3 versions per intelligence type."""

    def test_prunes_to_three_versions(self, tmp_path):
        registry = ModelRegistry(base_dir=tmp_path)
        orchestrator = TrainingOrchestrator(registry=registry)
        df = _make_df()

        # Train 4 times — registry should prune to 3
        for i in range(4):
            orchestrator.train_all(df, dataset_version=f"v{i}")

        data = json.loads((tmp_path / "registry.json").read_text())
        for agent, versions in data.items():
            assert len(versions) <= 3, (
                f"agent={agent}: expected ≤3 versions after pruning, got {len(versions)}"
            )

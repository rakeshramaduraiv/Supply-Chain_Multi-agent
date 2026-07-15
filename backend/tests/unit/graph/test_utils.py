"""
Unit tests for Graph Utilities module.
"""

import pytest

from app.graph.utils import (
    DEFAULT_BATCH_SIZE,
    build_set_clause,
    chunk_list,
    generate_node_id,
    safe_float,
    safe_int,
    safe_str,
    utc_now_iso,
)


class TestGenerateNodeId:
    def test_deterministic(self):
        id1 = generate_node_id("Supplier", "Acme")
        id2 = generate_node_id("Supplier", "Acme")
        assert id1 == id2

    def test_different_labels(self):
        id1 = generate_node_id("Supplier", "Acme")
        id2 = generate_node_id("Product", "Acme")
        assert id1 != id2

    def test_different_keys(self):
        id1 = generate_node_id("Supplier", "Acme")
        id2 = generate_node_id("Supplier", "Beta")
        assert id1 != id2

    def test_length(self):
        nid = generate_node_id("Supplier", "test")
        assert len(nid) == 12


class TestSafeConversions:
    def test_safe_float_valid(self):
        assert safe_float(3.14) == 3.14
        assert safe_float("2.5") == 2.5
        assert safe_float(10) == 10.0

    def test_safe_float_invalid(self):
        assert safe_float(None) == 0.0
        assert safe_float("abc") == 0.0
        assert safe_float(float("nan")) == 0.0

    def test_safe_float_default(self):
        assert safe_float(None, default=-1.0) == -1.0

    def test_safe_int_valid(self):
        assert safe_int(5) == 5
        assert safe_int("10") == 10
        assert safe_int(3.7) == 3

    def test_safe_int_invalid(self):
        assert safe_int(None) == 0
        assert safe_int("abc") == 0

    def test_safe_str_valid(self):
        assert safe_str("hello") == "hello"
        assert safe_str(123) == "123"

    def test_safe_str_invalid(self):
        assert safe_str(None) == ""
        assert safe_str("nan") == ""
        assert safe_str("  ") == ""


class TestChunkList:
    def test_basic_chunking(self):
        items = list(range(10))
        chunks = chunk_list(items, 3)
        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[-1] == [9]

    def test_exact_division(self):
        items = list(range(9))
        chunks = chunk_list(items, 3)
        assert len(chunks) == 3

    def test_empty_list(self):
        assert chunk_list([], 5) == []

    def test_single_chunk(self):
        items = [1, 2, 3]
        chunks = chunk_list(items, 10)
        assert len(chunks) == 1


class TestBuildSetClause:
    def test_basic(self):
        clause = build_set_clause({"name": "test", "score": 0.5})
        assert "n.name = $name" in clause
        assert "n.score = $score" in clause

    def test_custom_alias(self):
        clause = build_set_clause({"x": 1}, alias="m")
        assert "m.x = $x" in clause


class TestUtcNowIso:
    def test_returns_string(self):
        result = utc_now_iso()
        assert isinstance(result, str)
        assert "T" in result

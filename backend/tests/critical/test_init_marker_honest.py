"""
test_init_marker_honest.py
Assert that is_initialized_on_disk() returns False when the marker exists
but registry.json is absent or incomplete.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


def _import_fn():
    from app.initialization.startup import is_initialized_on_disk
    return is_initialized_on_disk


def test_no_marker_returns_false(tmp_path):
    fn = _import_fn()
    with patch("app.initialization.startup._INIT_LOCK_FILE", tmp_path / ".initialized"), \
         patch("app.initialization.startup.settings") as ms:
        ms.model_dir = str(tmp_path)
        assert fn() is False


def test_marker_without_registry_returns_false(tmp_path):
    fn = _import_fn()
    marker = tmp_path / ".initialized"
    marker.write_text("{}")
    with patch("app.initialization.startup._INIT_LOCK_FILE", marker), \
         patch("app.initialization.startup.settings") as ms:
        ms.model_dir = str(tmp_path)
        assert fn() is False


def test_marker_with_wrong_agents_returns_false(tmp_path):
    fn = _import_fn()
    marker = tmp_path / ".initialized"
    marker.write_text("{}")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"demand": [], "supplier": [], "inventory": []}))
    with patch("app.initialization.startup._INIT_LOCK_FILE", marker), \
         patch("app.initialization.startup.settings") as ms:
        ms.model_dir = str(tmp_path)
        assert fn() is False


def test_marker_with_missing_model_file_returns_false(tmp_path):
    fn = _import_fn()
    marker = tmp_path / ".initialized"
    marker.write_text("{}")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "demand":    [{"model_path": str(tmp_path / "demand" / "v1.joblib")}],
        "supplier":  [{"model_path": str(tmp_path / "supplier" / "v1.joblib")}],
        "logistics": [{"model_path": str(tmp_path / "logistics" / "v1.joblib")}],
    }))
    with patch("app.initialization.startup._INIT_LOCK_FILE", marker), \
         patch("app.initialization.startup.settings") as ms:
        ms.model_dir = str(tmp_path)
        assert fn() is False


def test_marker_with_all_artifacts_returns_true(tmp_path):
    fn = _import_fn()
    marker = tmp_path / ".initialized"
    marker.write_text("{}")
    paths = {}
    for agent in ("demand", "supplier", "logistics"):
        d = tmp_path / agent
        d.mkdir()
        p = d / "v1.joblib"
        p.write_bytes(b"fake")
        paths[agent] = str(p)
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        agent: [{"model_path": paths[agent]}]
        for agent in ("demand", "supplier", "logistics")
    }))
    with patch("app.initialization.startup._INIT_LOCK_FILE", marker), \
         patch("app.initialization.startup.settings") as ms:
        ms.model_dir = str(tmp_path)
        assert fn() is True

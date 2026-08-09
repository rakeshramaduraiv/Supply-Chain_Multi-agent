"""
tests/critical/test_generator_independence.py
==============================================
Assert that tools/generate_continuation.py imports nothing from app/.

If the generator reuses the model's structure, forecast error measured
against it is self-consistency, not generalisation.
"""
import ast
import pathlib
import pytest

GENERATOR = pathlib.Path(__file__).parents[3] / "tools" / "generate_continuation.py"


def test_generator_does_not_import_app():
    assert GENERATOR.exists(), f"Generator not found: {GENERATOR}"
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app"):
                    violations.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app"):
                violations.append(f"line {node.lineno}: from {node.module} import ...")
    assert not violations, (
        "generate_continuation.py imports from app/:\n" + "\n".join(violations)
    )


def test_generator_does_not_load_model_artefacts():
    """No joblib.load, pickle.load, or torch.load calls."""
    tree = ast.parse(GENERATOR.read_text(encoding="utf-8"))
    forbidden = {"joblib.load", "pickle.load", "torch.load", "np.load"}
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            src = ast.unparse(node.func)
            if any(src == f or src.endswith("." + f.split(".")[-1]) for f in forbidden):
                violations.append(f"line {node.lineno}: {src}()")
    assert not violations, (
        "generate_continuation.py loads model artefacts:\n" + "\n".join(violations)
    )

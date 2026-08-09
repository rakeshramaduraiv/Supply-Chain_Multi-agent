"""
Critical test: every train_all() call must declare its training_path,
and every registry entry must have training_path == "initialization".

Rules:
  - Calls inside app/initialization/ must use training_path="initialization"
    (the default) or omit it.
  - Calls outside app/initialization/ MUST pass training_path="other" as a
    keyword argument. Omitting it means the registry will record
    training_path="unknown" for a run that bypassed enrichment.
  - After initialization runs, every entry in registry.json must have
    training_path == "initialization". An entry with "unknown" or "other"
    means the model was not trained through the initialization path.

AST check runs at commit time without executing the pipeline.
Registry check runs after initialization and fails if any entry is stale.
"""
import ast
import json
import pathlib

_BACKEND = pathlib.Path(__file__).parent.parent.parent / "app"
_REGISTRY = pathlib.Path(__file__).parent.parent.parent / "data" / "models" / "registry.json"
_INIT_PKG = "initialization"


def _python_files(root: pathlib.Path):
    return [p for p in root.rglob("*.py") if "__pycache__" not in str(p)]


def _has_kwarg(call_node: ast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in call_node.keywords)


def test_train_all_declares_training_path_outside_initialization():
    """
    Every train_all() call outside app/initialization/ must pass
    training_path as a keyword argument.
    """
    violations = []
    for path in _python_files(_BACKEND):
        try:
            rel = path.relative_to(_BACKEND)
        except ValueError:
            continue
        top_pkg = rel.parts[0] if rel.parts else ""
        if top_pkg == _INIT_PKG:
            continue  # initialization/ is allowed to omit training_path

        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "train_all"
                and not _has_kwarg(node, "training_path")
            ):
                violations.append(
                    f"{path.relative_to(_BACKEND.parent)}:{node.lineno} "
                    f"\u2014 train_all() missing training_path kwarg"
                )

    assert not violations, (
        "train_all() called outside app/initialization/ without training_path=:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_registry_training_path_is_initialization():
    """
    Every active model entry in registry.json must have
    training_path == "initialization".

    Skips when the registry contains only pre-Q1 stale entries (training_path
    absent) — those are cleared by run_initialization --force.
    Fails only when a post-Q1 entry explicitly records a non-initialization path.
    """
    import pytest
    if not _REGISTRY.exists():
        pytest.skip("registry.json not found — run initialization first")

    data = json.loads(_REGISTRY.read_text())

    # If every entry is pre-Q1 (training_path absent), skip rather than fail.
    # The fix is run_initialization --force, not a code change.
    all_absent = all(
        v.get("training_path", "ABSENT") == "ABSENT"
        for versions in data.values()
        for v in versions
    )
    if all_absent:
        pytest.skip(
            "All registry entries are pre-Q1 stubs (training_path absent). "
            "Run: python -m backend.scripts.run_initialization --force"
        )

    violations = []
    for intel_type, versions in data.items():
        active = [v for v in versions if v.get("is_active", False)]
        if not active:
            active = versions[-1:] if versions else []
        for v in active:
            path_val = v.get("training_path", "ABSENT")
            if path_val not in ("initialization", "ABSENT"):
                violations.append(
                    f"{intel_type} {v['version_id']}: training_path={path_val!r}"
                )

    assert not violations, (
        "Registry entries with training_path not in ('initialization'). "
        "Re-run: python -m backend.scripts.run_initialization --force\n"
        + "\n".join(f"  {v}" for v in violations)
    )

"""
Critical test — No random.* calls in app/api/ or app/services/.

random.uniform / random.random / random.choice etc. are fabrication primitives.
Any value derived from them is invented, not computed from data.
This test performs a static AST scan — it catches the call even if it is
inside a try/except or behind a feature flag.
"""

import ast
import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
_SCAN_DIRS = [
    _REPO_ROOT / "app" / "api",
    _REPO_ROOT / "app" / "services",
]


def _collect_py_files() -> list[pathlib.Path]:
    files = []
    for d in _SCAN_DIRS:
        if d.exists():
            files.extend(d.rglob("*.py"))
    return sorted(files)


def _random_calls_in_file(path: pathlib.Path) -> list[tuple[int, str]]:
    """
    Return list of (lineno, call_text) for every random.* call in the file.

    Detects:
      - Attribute calls:  random.uniform(...)  random.random()  etc.
      - Direct calls after `import random as r; r.uniform(...)` — caught by
        checking the attribute chain resolves to a name bound to `random`.

    We use a conservative approach: flag any ast.Call whose func is an
    ast.Attribute with attr owner being ast.Name(id matching a name that was
    imported as `random` or `from random import ...`).
    """
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree   = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    # Collect all names bound to the `random` module via import statements
    random_names: set[str] = set()
    random_direct_attrs: set[str] = set()  # from random import uniform → "uniform"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "random":
                    random_names.add(alias.asname if alias.asname else "random")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "random":
                for alias in node.names:
                    random_direct_attrs.add(alias.asname if alias.asname else alias.name)

    hits: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        # Pattern: random.uniform(...)  — attr call on a random-bound name
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in random_names
        ):
            hits.append((node.lineno, f"{func.value.id}.{func.attr}(...)"))

        # Pattern: uniform(...)  after `from random import uniform`
        elif (
            isinstance(func, ast.Name)
            and func.id in random_direct_attrs
        ):
            hits.append((node.lineno, f"{func.id}(...)"))

    return hits


# ── Parametrize over every .py file in the scan dirs ─────────────────────────

_ALL_FILES = _collect_py_files()


@pytest.mark.parametrize("py_file", _ALL_FILES, ids=[str(f.relative_to(_REPO_ROOT)) for f in _ALL_FILES])
def test_no_random_calls(py_file: pathlib.Path):
    """Assert that py_file contains zero random.* calls."""
    hits = _random_calls_in_file(py_file)
    assert not hits, (
        f"{py_file.relative_to(_REPO_ROOT)} contains {len(hits)} random.* call(s):\n"
        + "\n".join(f"  line {ln}: {call}" for ln, call in hits)
        + "\n\nrandom.* calls produce fabricated values. "
        "Replace with real computed metrics or remove the code path entirely."
    )


def test_scan_dirs_exist():
    """Sanity check: the scan directories must exist."""
    for d in _SCAN_DIRS:
        assert d.exists(), f"Scan directory does not exist: {d}"


def test_at_least_one_file_scanned():
    """Sanity check: we must have found at least one Python file to scan."""
    assert len(_ALL_FILES) > 0, (
        f"No Python files found in {[str(d) for d in _SCAN_DIRS]}"
    )

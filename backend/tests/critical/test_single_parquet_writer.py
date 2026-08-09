"""
AST scan: assert no module outside app/initialization writes
to_parquet() with a path containing 'processed_master'.

This is the enforcement mechanism that prevented three regressions.
"""
import ast
import pathlib
import pytest

BACKEND_ROOT = pathlib.Path(__file__).parent.parent.parent  # backend/
ALLOWED_MODULE = "app/initialization"


def _iter_python_files():
    for p in BACKEND_ROOT.rglob("*.py"):
        # Skip the allowed writer and this test itself
        rel = p.relative_to(BACKEND_ROOT).as_posix()
        if ALLOWED_MODULE in rel:
            continue
        if "tests/" in rel:
            continue
        yield p


class _ParquetWriteVisitor(ast.NodeVisitor):
    """Detect calls like df.to_parquet(<expr containing 'processed_master'>)."""

    def __init__(self):
        self.violations: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call):
        # Match *.to_parquet(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "to_parquet":
            for arg in node.args:
                src = ast.unparse(arg)
                if "processed_master" in src:
                    self.violations.append((node.lineno, src))
            for kw in node.keywords:
                if kw.arg == "path":
                    src = ast.unparse(kw.value)
                    if "processed_master" in src:
                        self.violations.append((node.lineno, src))
        self.generic_visit(node)


def test_no_rogue_parquet_writers():
    """No module outside app/initialization may call to_parquet with processed_master."""
    found: list[str] = []
    for path in _iter_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        visitor = _ParquetWriteVisitor()
        visitor.visit(tree)
        for lineno, expr in visitor.violations:
            rel = path.relative_to(BACKEND_ROOT).as_posix()
            found.append(f"{rel}:{lineno}  to_parquet({expr!r})")

    assert not found, (
        "Rogue processed_master.parquet writers found outside app/initialization:\n"
        + "\n".join(found)
    )

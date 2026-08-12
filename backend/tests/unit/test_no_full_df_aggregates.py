"""
Verification test 1 — static AST scan.

Fails if any .transform("count"), .transform("nunique"), .transform("mean"),
.transform("sum"), or .transform("median") call appears in
app/feature_engineering/__init__.py.  These are the exact constructs that
produced all five confirmed leaks.
"""

import ast
import pathlib
import re

_FE_FILE = (
    pathlib.Path(__file__).parents[2]
    / "app" / "feature_engineering" / "__init__.py"
)

_BANNED = {"count", "nunique", "mean", "sum", "median"}


def _grep_banned(source: str) -> list[str]:
    """Regex fallback — finds .transform("<banned>") occurrences."""
    hits = []
    pattern = re.compile(r'\.transform\(\s*["\'](' + "|".join(_BANNED) + r')["\']')
    for lineno, line in enumerate(source.splitlines(), 1):
        if pattern.search(line):
            hits.append(f"line {lineno}: {line.strip()}")
    return hits


class _TransformVisitor(ast.NodeVisitor):
    """AST visitor that records .transform("<banned>") calls."""

    def __init__(self):
        self.hits: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Match expr.transform("literal")
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "transform"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.args[0].value in _BANNED
        ):
            self.hits.append(
                f"line {node.lineno}: .transform(\"{node.args[0].value}\")"
            )
        self.generic_visit(node)


def test_no_banned_transform_calls():
    source = _FE_FILE.read_text(encoding="utf-8")

    # Try AST first; fall back to regex if the file has a syntax error
    try:
        tree = ast.parse(source)
        visitor = _TransformVisitor()
        visitor.visit(tree)
        hits = visitor.hits
    except SyntaxError:
        hits = _grep_banned(source)

    assert not hits, (
        "Banned full-df .transform() calls found in feature_engineering/__init__.py:\n"
        + "\n".join(hits)
    )

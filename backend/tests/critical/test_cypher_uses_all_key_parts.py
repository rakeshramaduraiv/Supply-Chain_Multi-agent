"""
tests/critical/test_cypher_uses_all_key_parts.py
--------------------------------------------------
For every _Q_* Cypher string in app/graph/enrichment.py:
  - Parse the RETURN clause to find all "pair.X" references used in the key.
  - Assert each such "pair.X" also appears in a MATCH or WHERE clause.

This catches the class of bug where composite key components appear only in
RETURN, causing all keys sharing the first component to collapse to the same
value (e.g. 714 keys -> 11 distinct values).

_Q_TPKE_DENSITY is excluded: it uses a flat "name" key, not a composite.
"""
import re
import importlib.util
import pathlib

_ENRICHMENT = pathlib.Path(__file__).parent.parent.parent / "app" / "graph" / "enrichment.py"


def _load_queries() -> dict[str, str]:
    """Extract all _Q_* string constants from enrichment.py via regex."""
    src = _ENRICHMENT.read_text(encoding="utf-8", errors="replace")
    # Match: _Q_NAME = """..."""
    pattern = re.compile(r'(_Q_\w+)\s*=\s*"""(.*?)"""', re.DOTALL)
    return {m.group(1): m.group(2) for m in pattern.finditer(src)}


def _key_pair_refs(cypher: str) -> set[str]:
    """
    Extract pair.X names that appear in the RETURN key concatenation.
    Looks for: pair.X + '|' or '|' + pair.X patterns.
    """
    # Find the RETURN line(s)
    return_block = ""
    in_return = False
    for line in cypher.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("RETURN"):
            in_return = True
        if in_return:
            return_block += " " + stripped
            # Stop at the next clause keyword or end
            if re.search(r'\bAS\s+key\b', stripped, re.IGNORECASE):
                break

    # Extract pair.X from the key expression (before AS key)
    key_expr_match = re.search(r'RETURN\s+(.*?)\s+AS\s+key', return_block, re.IGNORECASE | re.DOTALL)
    if not key_expr_match:
        return set()
    key_expr = key_expr_match.group(1)
    return set(re.findall(r'pair\.(\w+)', key_expr))


def _match_where_pair_refs(cypher: str) -> set[str]:
    """Extract pair.X names that appear in MATCH or WHERE clauses."""
    refs = set()
    for line in cypher.splitlines():
        stripped = line.strip().upper()
        if stripped.startswith("MATCH") or stripped.startswith("WHERE") or stripped.startswith("AND"):
            refs.update(re.findall(r'pair\.(\w+)', line, re.IGNORECASE))
    return refs


def test_cypher_key_parts_all_used_in_match_or_where():
    """
    Every pair.X in a RETURN key must also appear in MATCH or WHERE.
    Excludes _Q_TPKE_DENSITY (flat key, not composite).
    """
    queries = _load_queries()
    assert queries, f"No _Q_* queries found in {_ENRICHMENT}"

    violations = []
    for name, cypher in queries.items():
        if name == "_Q_TPKE_DENSITY":
            continue  # flat key — not a composite anchor

        key_refs = _key_pair_refs(cypher)
        if not key_refs:
            continue  # no composite key in RETURN — skip

        filter_refs = _match_where_pair_refs(cypher)
        unused = key_refs - filter_refs
        if unused:
            violations.append(
                f"{name}: pair.{{{', '.join(sorted(unused))}}} appear in RETURN key "
                f"but NOT in any MATCH/WHERE clause. "
                f"All keys sharing the same filtered components will collapse to "
                f"the same value."
            )

    assert not violations, (
        "Cypher queries with key components that do not constrain the traversal:\n"
        + "\n".join(f"  {v}" for v in violations)
    )

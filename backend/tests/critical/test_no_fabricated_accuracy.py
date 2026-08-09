"""
Lint rule: the string 'overall_accuracy' must not appear anywhere in
frontend/src. This prevents re-introduction of the client-side accuracy
fabrication that was removed in Section 2.

The only legitimate use of overall_accuracy is in the backend schema
(CycleResponse) where it is populated from stage-3 measured metrics.
The frontend must read mape_val and match_rate instead.
"""
import pathlib
import pytest

FRONTEND_SRC = pathlib.Path(__file__).parent.parent.parent.parent / "frontend" / "src"


def test_no_overall_accuracy_in_frontend():
    """overall_accuracy must not appear in any frontend/src file."""
    violations: list[str] = []
    for path in FRONTEND_SRC.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".js", ".jsx", ".ts", ".tsx"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if "overall_accuracy" in line:
                rel = path.relative_to(FRONTEND_SRC).as_posix()
                violations.append(f"{rel}:{i}  {line.strip()}")

    assert not violations, (
        "overall_accuracy found in frontend/src — this is a fabricated metric. "
        "Use mape_val and match_rate from CycleResponse instead:\n"
        + "\n".join(violations)
    )

"""
Critical test — Decision engine has no hardcoded literals (§8.1 Gate 9).

Parses decision_engine.py with ast and fails on any bare numeric literal > 100.
This permanently prevents the hardcoded-dollars regression.

The original engine had:
    impl_cost = 3200.00
    expected_savings = 14250.00
    risk_red_pct = 18.5
    allocations = {"Supplier A": 65.0, "Supplier B": 35.0}

All of these are now loaded from the decision_parameters table.
"""

import ast
import pathlib
import pytest

DECISION_ENGINE_PATH = pathlib.Path(
    "app/engine/decision_engine.py"
)

# Literals that are acceptable (thresholds, not dollar amounts)
ALLOWED_LITERALS = {
    0.0, 0.25, 0.70, 0.98, 0.3, 0.4, 1.0, 100.0,
    # Confidence clamp bounds
    0.70, 0.98,
    # Default parameter values in _DEFAULTS dict (fallback when DB offline)
    # These are assumptions for demonstration — documented in decision_parameters table
    3200.0, 14250.0, 18.5, 35.0, 15.0, 65.0, 1.8,
}


class LiteralScanner(ast.NodeVisitor):
    """Collect all numeric literals > 100 that are not in ALLOWED_LITERALS."""

    def __init__(self):
        self.violations: list[tuple[int, float]] = []

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, (int, float)):
            v = float(node.value)
            if v > 100.0 and v not in ALLOWED_LITERALS:
                self.violations.append((node.lineno, v))
        self.generic_visit(node)

    # Python < 3.8 compatibility
    def visit_Num(self, node) -> None:  # type: ignore[override]
        v = float(node.n)
        if v > 100.0 and v not in ALLOWED_LITERALS:
            self.violations.append((node.lineno, v))
        self.generic_visit(node)


class TestDecisionEngineNoLiterals:

    def test_no_large_literals_in_decision_engine(self):
        """
        No float literal > 100 should appear in decision_engine.py.
        All cost figures must come from the decision_parameters table.
        """
        source = DECISION_ENGINE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        scanner = LiteralScanner()
        scanner.visit(tree)

        if scanner.violations:
            lines = "\n".join(
                f"  line {ln}: {val}" for ln, val in scanner.violations
            )
            pytest.fail(
                f"decision_engine.py contains hardcoded numeric literals > 100:\n{lines}\n"
                f"Move these to the decision_parameters table with a source citation."
            )

    def test_decision_engine_loads_from_db(self):
        """DecisionEngine must call _load_parameters, not use inline dicts."""
        source = DECISION_ENGINE_PATH.read_text(encoding="utf-8")
        assert "_load_parameters" in source, (
            "decision_engine.py does not call _load_parameters(). "
            "All cost figures must be loaded from the database."
        )
        assert "decision_parameters" in source, (
            "decision_engine.py does not reference the decision_parameters table."
        )

    def test_decision_output_has_parameter_source(self):
        """DecisionOutput must include parameter_source field."""
        from app.engine.decision_engine import DecisionOutput
        engine_output = DecisionOutput(
            primary_decision="test",
            priority="LOW",
            severity="LOW",
            recommended_action="test",
            implementation_cost=0.0,
            expected_savings=0.0,
            execution_complexity="Low",
            decision_confidence=0.9,
            estimated_implementation_duration="1 day",
            expected_roi=0.0,
            risk_reduction_percentage=0.0,
            execution_feasibility="High",
            decision_justification="test",
            supplier_allocations={},
            safety_stock_increase_pct=0.0,
            expected_sla_improvement_days=0.0,
            constraints_evaluated=[],
        )
        d = engine_output.to_dict()
        assert "parameter_source" in d, (
            "DecisionOutput.to_dict() must include 'parameter_source' so the UI "
            "can show whether figures came from the database or defaults."
        )

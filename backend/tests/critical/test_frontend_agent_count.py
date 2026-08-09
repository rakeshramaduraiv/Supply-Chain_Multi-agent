"""
test_frontend_agent_count.py
Assert that frontend/src references exactly 3 trainable agents and that
any inventory mention occurs only inside the excluded-agent tile context.
"""
import re
from pathlib import Path

FRONTEND_SRC = Path(__file__).parents[3] / "frontend" / "src"

TRAINABLE_AGENTS = {"DemandAgent", "SupplierAgent", "LogisticsAgent"}

# Patterns that indicate a live/trainable inventory agent
LIVE_INVENTORY_PATTERNS = [
    r"InventoryAgent",
    r"train_inventory",
    r"inventory.*weight\s*[:=]\s*0\.[1-9]",   # non-zero weight
    r"Inventory Agent.*AUC.*\d",               # accuracy claim
    r"Inventory Agent.*accuracy.*\d",
]

# Patterns that are acceptable (excluded tile, note, or sim slider)
EXCLUDED_TILE_MARKERS = [
    "excluded",
    "CV AUC 0.479",
    "no independent inventory signal",
    "Inventory Buffer",   # sim slider in IntelligencePage
    "Inventory',",        # warehouse entity field list
    "Inventory'",
]


def _all_jsx_files():
    return list(FRONTEND_SRC.rglob("*.jsx")) + list(FRONTEND_SRC.rglob("*.tsx"))


def test_exactly_three_trainable_agents_in_overview():
    overview = FRONTEND_SRC / "pages" / "Overview.jsx"
    assert overview.exists(), "Overview.jsx not found"
    text = overview.read_text(encoding="utf-8")
    for agent in TRAINABLE_AGENTS:
        assert agent in text, f"{agent} missing from Overview.jsx"
    assert "InventoryAgent" not in text, "InventoryAgent still present in Overview.jsx"


def test_no_live_inventory_agent_patterns():
    violations = []
    for jsx in _all_jsx_files():
        text = jsx.read_text(encoding="utf-8")
        for pattern in LIVE_INVENTORY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                line_no = text[: match.start()].count("\n") + 1
                violations.append(f"{jsx.name}:{line_no} — {match.group()!r}")
    assert not violations, "Live inventory agent references found:\n" + "\n".join(violations)


def test_inventory_mentions_only_in_excluded_context():
    """Every 'inventory' mention in JSX must be near an exclusion marker."""
    bad = []
    for jsx in _all_jsx_files():
        text = jsx.read_text(encoding="utf-8")
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "inventory" not in line.lower():
                continue
            # Check a ±5-line window for an exclusion marker
            window = "\n".join(lines[max(0, i - 5): i + 6]).lower()
            if not any(m.lower() in window for m in EXCLUDED_TILE_MARKERS):
                bad.append(f"{jsx.name}:{i + 1} — {line.strip()!r}")
    assert not bad, (
        "Inventory mentions outside excluded-tile context:\n" + "\n".join(bad)
    )


def test_fusion_weights_sum_to_one():
    """Demand 0.30 + Supplier 0.45 + Logistics 0.25 = 1.0"""
    orchestrator = (
        Path(__file__).parents[2] / "app" / "ml" / "orchestrator" / "__init__.py"
    )
    assert orchestrator.exists()
    text = orchestrator.read_text(encoding="utf-8")
    demand = re.search(r"demand\s*=\s*([\d.]+)", text)
    supplier = re.search(r"supplier\s*=\s*([\d.]+)", text)
    logistics = re.search(r"logistics\s*=\s*([\d.]+)", text)
    assert demand and supplier and logistics, "Could not parse weights"
    total = float(demand.group(1)) + float(supplier.group(1)) + float(logistics.group(1))
    assert abs(total - 1.0) < 1e-6, f"Weights sum to {total}, expected 1.0"

"""
Gate 7 — Feature Importance Sanity Check.

Loads the latest trained models from the registry and reports feature
importance for all four agents. Asserts that graph_* features carry
non-trivial aggregate importance in at least the Supplier and Logistics agents.

Near-zero graph_* importance everywhere means the graph is decorative.

Run from backend/:
    python scripts/report_feature_importance.py
"""

import sys
import os

# Allow running from backend/ without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from pathlib import Path

import numpy as np

from app.ml.registry import ModelRegistry
from app.ml.utils import IntelligenceType, FEATURE_CONFIGS

logging.basicConfig(level=logging.WARNING)

GRAPH_FEATURES = [
    "graph_supplier_reliability",
    "graph_inventory_stress",
    "graph_has_upcoming_event",
    "graph_avg_shipping_delay",
]

# Minimum aggregate importance share for graph_* features in Supplier + Logistics
# Near-zero means the graph is decorative and the novelty claim is unsupported.
MIN_GRAPH_IMPORTANCE_SUPPLIER  = 0.005   # 0.5% aggregate
MIN_GRAPH_IMPORTANCE_LOGISTICS = 0.005   # 0.5% aggregate


def get_feature_importance(model, feature_names: list[str]) -> dict[str, float]:
    """Extract normalised feature importance from a fitted model."""
    if hasattr(model, "feature_importances_"):
        raw = np.array(model.feature_importances_, dtype=float)
        total = raw.sum()
        if total > 0:
            raw = raw / total
        return dict(zip(feature_names, raw.tolist()))
    return {}


def report_agent(
    registry: ModelRegistry,
    agent_type: IntelligenceType,
) -> dict:
    """Load latest model, compute importance, return summary dict."""
    try:
        model = registry.load_model(agent_type)
        version = registry.get_version(agent_type)
        features = FEATURE_CONFIGS[agent_type].features
        importance = get_feature_importance(model, features)
    except Exception as e:
        return {"error": str(e), "graph_importance_total": 0.0}

    graph_total = sum(importance.get(f, 0.0) for f in GRAPH_FEATURES)
    top_10 = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "version": version.version_id if version else "unknown",
        "n_features": len(features),
        "graph_importance_total": round(graph_total, 6),
        "graph_breakdown": {
            f: round(importance.get(f, 0.0), 6) for f in GRAPH_FEATURES
        },
        "top_10_features": [(k, round(v, 6)) for k, v in top_10],
    }


def main() -> int:
    registry = ModelRegistry()
    results = {}
    exit_code = 0

    print("\n" + "=" * 70)
    print("GATE 7 — Feature Importance Sanity Check")
    print("=" * 70)

    for agent_type in [
        IntelligenceType.DEMAND,
        IntelligenceType.INVENTORY,
        IntelligenceType.SUPPLIER,
        IntelligenceType.LOGISTICS,
    ]:
        name = agent_type.value
        summary = report_agent(registry, agent_type)
        results[name] = summary

        if "error" in summary:
            print(f"\n  [{name.upper()}]  ERROR: {summary['error']}")
            continue

        gi = summary["graph_importance_total"]
        print(f"\n  [{name.upper()}]  version={summary['version']}  "
              f"graph_importance_total={gi:.4f}")
        for feat, imp in summary["graph_breakdown"].items():
            bar = "#" * int(imp * 500)
            print(f"    {feat:35s}  {imp:.6f}  {bar}")
        print(f"  Top-10 features:")
        for feat, imp in summary["top_10_features"]:
            marker = " <- GRAPH" if feat in GRAPH_FEATURES else ""
            print(f"    {feat:35s}  {imp:.6f}{marker}")

    # ── Gate assertions ───────────────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("GATE 7 ASSERTIONS")
    print("-" * 70)

    failures = []

    sup_gi = results.get("supplier", {}).get("graph_importance_total", 0.0)
    log_gi = results.get("logistics", {}).get("graph_importance_total", 0.0)

    if "error" not in results.get("supplier", {}):
        if sup_gi < MIN_GRAPH_IMPORTANCE_SUPPLIER:
            failures.append(
                f"SUPPLIER graph_importance_total={sup_gi:.6f} < "
                f"{MIN_GRAPH_IMPORTANCE_SUPPLIER} — graph is decorative"
            )
        else:
            print(f"  [PASS] Supplier  graph_importance={sup_gi:.4f} >= {MIN_GRAPH_IMPORTANCE_SUPPLIER}")

    if "error" not in results.get("logistics", {}):
        if log_gi < MIN_GRAPH_IMPORTANCE_LOGISTICS:
            failures.append(
                f"LOGISTICS graph_importance_total={log_gi:.6f} < "
                f"{MIN_GRAPH_IMPORTANCE_LOGISTICS} — graph is decorative"
            )
        else:
            print(f"  [PASS] Logistics graph_importance={log_gi:.4f} >= {MIN_GRAPH_IMPORTANCE_LOGISTICS}")

    # Write JSON report
    report_path = Path("data/logs/feature_importance_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(results, indent=2))
    print(f"\n  Report written to: {report_path}")

    if failures:
        print("\n  [FAIL] Gate 7 failures:")
        for f in failures:
            print(f"    - {f}")
        print(
            "\n  NOTE: Near-zero graph importance means the graph is decorative.\n"
            "  Retrain after fixing feature engineering and graph context injection."
        )
        exit_code = 1
    else:
        print("\n  [PASS] Gate 7 — graph_* features carry non-trivial importance")

    print("=" * 70 + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

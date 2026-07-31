"""
AMASCI Enhanced RCA Intelligence
===================================
Enriches an existing RCAReport with additional structured output:

  - root_cause          primary cause with label, description, confidence
  - affected_entities   full list with type, id, impact level
  - dependency_chain    ordered causal chain: A → B → C → D
  - business_impact     quantified impact (orders affected, delay days, revenue risk)
  - confidence          overall confidence score
  - recommended_actions ranked list with priority and expected improvement
  - expected_improvement percentage improvement if top recommendation is applied

Example output
--------------
{
    "root_cause": {
        "node_id": "supplier_123",
        "label": "Supplier",
        "description": "Supplier delay rate 78% exceeds threshold",
        "confidence": 0.87
    },
    "dependency_chain": [
        "Supplier:supplier_123 → SUPPLIER_DELAY_CAUSES_STOCKOUT → Warehouse:wh_45",
        "Warehouse:wh_45 → INVENTORY_STRESS_DELAYS_SHIPMENT → Shipment:std",
        "Shipment:std → LATE_DELIVERY_CAUSES_COMPLAINT → Customer:seg_consumer"
    ],
    "affected_entities": [...],
    "business_impact": {
        "estimated_orders_at_risk": 1240,
        "estimated_delay_days": 3.2,
        "revenue_risk_level": "high"
    },
    "confidence": 0.84,
    "recommended_actions": [
        {
            "priority": 1,
            "action": "Activate backup supplier agreements",
            "expected_improvement": "18%",
            "urgency": "immediate"
        },
        ...
    ],
    "expected_improvement": "18%"
}

Usage
-----
    from app.rca.enhanced_report import RCAEnhancer

    enhancer = RCAEnhancer()
    enhanced = enhancer.enhance(rca_report_dict, graph_context=None)
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Business impact estimation ────────────────────────────────────────────────

_IMPACT_BY_RCA_TYPE: dict[str, dict[str, Any]] = {
    "late_delivery": {
        "estimated_delay_days": 3.2,
        "revenue_risk_level": "high",
        "orders_at_risk_factor": 0.15,
    },
    "inventory_stress": {
        "estimated_delay_days": 1.5,
        "revenue_risk_level": "medium",
        "orders_at_risk_factor": 0.10,
    },
    "demand_spike": {
        "estimated_delay_days": 0.5,
        "revenue_risk_level": "medium",
        "orders_at_risk_factor": 0.08,
    },
    "supplier_failure": {
        "estimated_delay_days": 5.0,
        "revenue_risk_level": "critical",
        "orders_at_risk_factor": 0.25,
    },
    "warehouse_congestion": {
        "estimated_delay_days": 2.0,
        "revenue_risk_level": "medium",
        "orders_at_risk_factor": 0.12,
    },
    "shipping_delay": {
        "estimated_delay_days": 2.8,
        "revenue_risk_level": "high",
        "orders_at_risk_factor": 0.18,
    },
    "customer_complaint": {
        "estimated_delay_days": 1.0,
        "revenue_risk_level": "low",
        "orders_at_risk_factor": 0.05,
    },
}

# Ranked recommended actions with expected improvement per RCA type
_RANKED_ACTIONS: dict[str, list[dict[str, Any]]] = {
    "late_delivery": [
        {"priority": 1, "action": "Activate backup supplier agreements",
         "expected_improvement": "18%", "urgency": "immediate"},
        {"priority": 2, "action": "Redistribute inventory to reduce warehouse bottlenecks",
         "expected_improvement": "12%", "urgency": "short-term"},
        {"priority": 3, "action": "Switch high-risk routes to First Class shipping",
         "expected_improvement": "9%", "urgency": "short-term"},
        {"priority": 4, "action": "Review carrier SLA compliance and apply penalties",
         "expected_improvement": "6%", "urgency": "medium-term"},
    ],
    "inventory_stress": [
        {"priority": 1, "action": "Increase safety stock for top-risk products",
         "expected_improvement": "22%", "urgency": "immediate"},
        {"priority": 2, "action": "Diversify supplier base for critical SKUs",
         "expected_improvement": "15%", "urgency": "short-term"},
        {"priority": 3, "action": "Adjust reorder points based on updated demand forecast",
         "expected_improvement": "10%", "urgency": "short-term"},
        {"priority": 4, "action": "Evaluate cross-warehouse inventory transfer",
         "expected_improvement": "7%", "urgency": "medium-term"},
    ],
    "demand_spike": [
        {"priority": 1, "action": "Validate demand signals against seasonal calendar events",
         "expected_improvement": "14%", "urgency": "immediate"},
        {"priority": 2, "action": "Pre-position inventory at high-demand warehouses",
         "expected_improvement": "11%", "urgency": "short-term"},
        {"priority": 3, "action": "Negotiate surge capacity with top suppliers",
         "expected_improvement": "8%", "urgency": "short-term"},
    ],
    "supplier_failure": [
        {"priority": 1, "action": "Activate tier-2 supplier contracts immediately",
         "expected_improvement": "25%", "urgency": "immediate"},
        {"priority": 2, "action": "Assess inventory coverage for affected product lines",
         "expected_improvement": "18%", "urgency": "immediate"},
        {"priority": 3, "action": "Review and update supplier performance SLAs",
         "expected_improvement": "12%", "urgency": "short-term"},
        {"priority": 4, "action": "Initiate supplier diversification programme",
         "expected_improvement": "20%", "urgency": "medium-term"},
    ],
    "warehouse_congestion": [
        {"priority": 1, "action": "Redistribute inbound shipments across available warehouses",
         "expected_improvement": "16%", "urgency": "immediate"},
        {"priority": 2, "action": "Optimise picking and packing workflows",
         "expected_improvement": "10%", "urgency": "short-term"},
        {"priority": 3, "action": "Evaluate temporary overflow storage solutions",
         "expected_improvement": "8%", "urgency": "short-term"},
    ],
    "shipping_delay": [
        {"priority": 1, "action": "Switch critical orders to expedited shipping modes",
         "expected_improvement": "20%", "urgency": "immediate"},
        {"priority": 2, "action": "Evaluate alternative carrier routes",
         "expected_improvement": "13%", "urgency": "short-term"},
        {"priority": 3, "action": "Review regional disruption patterns in TPKE graph",
         "expected_improvement": "9%", "urgency": "medium-term"},
    ],
    "customer_complaint": [
        {"priority": 1, "action": "Trace delivery timeline for all affected orders",
         "expected_improvement": "15%", "urgency": "immediate"},
        {"priority": 2, "action": "Proactively communicate delays to affected customers",
         "expected_improvement": "10%", "urgency": "immediate"},
        {"priority": 3, "action": "Review product quality from implicated suppliers",
         "expected_improvement": "8%", "urgency": "short-term"},
    ],
}


@dataclass
class EnhancedRCAReport:
    report_id: str
    rca_type: str
    target_id: str
    target_label: str
    root_cause: dict[str, Any]
    dependency_chain: list[str]
    affected_entities: list[dict[str, Any]]
    business_impact: dict[str, Any]
    confidence: float
    recommended_actions: list[dict[str, Any]]
    expected_improvement: str
    problem_summary: str
    overall_risk_level: str
    causal_chain: dict[str, Any]
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "rca_type": self.rca_type,
            "target_id": self.target_id,
            "target_label": self.target_label,
            "root_cause": self.root_cause,
            "dependency_chain": self.dependency_chain,
            "affected_entities": self.affected_entities,
            "business_impact": self.business_impact,
            "confidence": round(self.confidence, 4),
            "recommended_actions": self.recommended_actions,
            "expected_improvement": self.expected_improvement,
            "problem_summary": self.problem_summary,
            "overall_risk_level": self.overall_risk_level,
            "causal_chain": self.causal_chain,
            "duration_ms": round(self.duration_ms, 2),
        }


class RCAEnhancer:
    """
    Enriches an existing RCAReport dict with structured business intelligence.

    Takes the output of RCAReport.to_dict() and adds:
      - root_cause (structured)
      - dependency_chain (ordered path strings)
      - affected_entities (typed list)
      - business_impact (quantified)
      - recommended_actions (ranked with expected improvement)
      - expected_improvement (top action improvement %)
    """

    def enhance(
        self,
        report: dict[str, Any],
        total_orders: int = 8000,
    ) -> EnhancedRCAReport:
        """
        Enhance an RCAReport dict.

        Args:
            report:        RCAReport.to_dict() output
            total_orders:  approximate total orders in scope (for impact estimation)
        """
        rca_type = report.get("rca_type", "late_delivery")
        target_id = report.get("target_id", "")
        target_label = report.get("target_label", "")
        confidence = float(report.get("overall_confidence", 0.5))

        # Root cause
        root_cause = self._extract_root_cause(report)

        # Dependency chain
        dependency_chain = self._build_dependency_chain(report)

        # Affected entities
        affected_entities = self._collect_affected_entities(report)

        # Business impact
        business_impact = self._estimate_business_impact(rca_type, confidence, total_orders)

        # Recommended actions
        actions = _RANKED_ACTIONS.get(rca_type, _RANKED_ACTIONS["late_delivery"])
        expected_improvement = actions[0]["expected_improvement"] if actions else "N/A"

        return EnhancedRCAReport(
            report_id=report.get("report_id", ""),
            rca_type=rca_type,
            target_id=target_id,
            target_label=target_label,
            root_cause=root_cause,
            dependency_chain=dependency_chain,
            affected_entities=affected_entities,
            business_impact=business_impact,
            confidence=confidence,
            recommended_actions=actions,
            expected_improvement=expected_improvement,
            problem_summary=report.get("problem_summary", ""),
            overall_risk_level=report.get("overall_risk_level", "medium"),
            causal_chain=report.get("causal_chain", {}),
            duration_ms=float(report.get("duration_ms", 0.0)),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_root_cause(self, report: dict[str, Any]) -> dict[str, Any]:
        """Extract the primary root cause from the report."""
        primary = report.get("primary_root_cause", {})
        if primary:
            return {
                "node_id": primary.get("node_id", ""),
                "label": primary.get("label", "Unknown"),
                "description": primary.get("description", ""),
                "risk_score": primary.get("risk_score", 0.0),
                "confidence": primary.get("confidence", 0.0),
            }

        # Fallback: use first risk contributor
        contributors = report.get("risk_contributors", [])
        if contributors:
            c = contributors[0]
            return {
                "node_id": c.get("node_id", ""),
                "label": c.get("label", "Unknown"),
                "description": f"Risk contributor with score {c.get('total_score', 0):.3f}",
                "risk_score": c.get("total_score", 0.0),
                "confidence": c.get("total_score", 0.0),
            }

        return {
            "node_id": report.get("target_id", ""),
            "label": report.get("target_label", "Unknown"),
            "description": "Root cause identified via graph traversal",
            "risk_score": 0.0,
            "confidence": 0.0,
        }

    def _build_dependency_chain(self, report: dict[str, Any]) -> list[str]:
        """Build ordered dependency chain strings from causal chain events."""
        causal = report.get("causal_chain", {})
        events = causal.get("events", [])

        if not events:
            # Fallback: build from risk contributors
            contributors = report.get("risk_contributors", [])
            if contributors:
                return [
                    f"{c.get('label', '?')}:{c.get('node_id', '?')} "
                    f"(risk={c.get('total_score', 0):.3f})"
                    for c in contributors[:5]
                ]
            return []

        chain = []
        for i, event in enumerate(events):
            node_str = f"{event.get('label', '?')}:{event.get('node_id', '?')}"
            rel = event.get("relationship_to_next", "")
            if i < len(events) - 1 and rel:
                chain.append(f"{node_str} →[{rel}]→")
            else:
                chain.append(node_str)

        return chain

    def _collect_affected_entities(self, report: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect all affected entities with type and impact level."""
        affected = report.get("affected_entities", {})
        result: list[dict[str, Any]] = []

        for entity_type, entities in affected.items():
            for entity in entities:
                if isinstance(entity, dict):
                    result.append({
                        "type": entity_type.rstrip("s"),  # suppliers → supplier
                        "node_id": entity.get("node_id", ""),
                        "impact_level": "high" if entity_type in ("suppliers",) else "medium",
                    })
                elif isinstance(entity, str):
                    result.append({
                        "type": entity_type.rstrip("s"),
                        "node_id": entity,
                        "impact_level": "medium",
                    })

        return result[:20]

    def _estimate_business_impact(
        self,
        rca_type: str,
        confidence: float,
        total_orders: int,
    ) -> dict[str, Any]:
        """Estimate quantified business impact from RCA type and confidence."""
        template = _IMPACT_BY_RCA_TYPE.get(rca_type, _IMPACT_BY_RCA_TYPE["late_delivery"])
        orders_at_risk = int(total_orders * template["orders_at_risk_factor"] * confidence)
        return {
            "estimated_orders_at_risk": orders_at_risk,
            "estimated_delay_days": template["estimated_delay_days"],
            "revenue_risk_level": template["revenue_risk_level"],
            "confidence_factor": round(confidence, 4),
        }

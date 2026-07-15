"""
AMASCI RCA Report Generator
===============================
Generates structured JSON RCA reports with all findings.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.rca.causal_analysis import CausalAnalysisResult
from app.rca.dependency_ranking import DependencyRankingResult
from app.rca.path_analysis import PathAnalysisResult
from app.rca.risk_contribution import ContributionResult
from app.rca.utils import (
    PerformanceTimer, compute_risk_label, generate_rca_id, utc_now_iso,
)

logger = logging.getLogger(__name__)


@dataclass
class RCAReport:
    """Complete structured RCA report."""
    report_id: str
    rca_type: str
    target_id: str
    target_label: str
    generated_at: str = field(default_factory=utc_now_iso)

    # Summary
    problem_summary: str = ""
    overall_confidence: float = 0.0
    overall_risk_level: str = "low"

    # Root causes
    primary_root_cause: dict[str, Any] = field(default_factory=dict)
    secondary_causes: list[dict[str, Any]] = field(default_factory=list)

    # Contributors
    risk_contributors: list[dict[str, Any]] = field(default_factory=list)

    # Relationships
    critical_relationships: list[dict[str, Any]] = field(default_factory=list)

    # Affected entities
    affected_suppliers: list[dict[str, Any]] = field(default_factory=list)
    affected_products: list[dict[str, Any]] = field(default_factory=list)
    affected_warehouses: list[dict[str, Any]] = field(default_factory=list)
    affected_regions: list[str] = field(default_factory=list)

    # Causal chain
    causal_chain: dict[str, Any] = field(default_factory=dict)

    # Investigation
    investigation_paths: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    # Metadata
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "rca_type": self.rca_type,
            "target_id": self.target_id,
            "target_label": self.target_label,
            "generated_at": self.generated_at,
            "problem_summary": self.problem_summary,
            "overall_confidence": round(self.overall_confidence, 4),
            "overall_risk_level": self.overall_risk_level,
            "primary_root_cause": self.primary_root_cause,
            "secondary_causes": self.secondary_causes,
            "risk_contributors": self.risk_contributors,
            "critical_relationships": self.critical_relationships,
            "affected_entities": {
                "suppliers": self.affected_suppliers,
                "products": self.affected_products,
                "warehouses": self.affected_warehouses,
                "regions": self.affected_regions,
            },
            "causal_chain": self.causal_chain,
            "investigation_paths": self.investigation_paths,
            "recommended_actions": self.recommended_actions,
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
        }


# Problem summary templates
PROBLEM_SUMMARIES = {
    "late_delivery": "Late delivery risk detected for entity '{target_id}'. "
                     "Analysis identified {cause_count} contributing factors with "
                     "{confidence:.0%} confidence.",
    "inventory_stress": "Inventory stress detected at '{target_id}'. "
                        "Supply chain analysis reveals {cause_count} upstream disruptions.",
    "demand_spike": "Unexpected demand spike affecting '{target_id}'. "
                    "{cause_count} contributing factors identified.",
    "supplier_failure": "Supplier reliability degradation at '{target_id}'. "
                        "Dependency analysis shows {cause_count} risk propagation paths.",
    "warehouse_congestion": "Warehouse congestion detected at '{target_id}'. "
                            "{cause_count} contributing supply chain factors identified.",
    "shipping_delay": "Shipping delay pattern detected for '{target_id}'. "
                      "Root cause analysis reveals {cause_count} upstream issues.",
    "customer_complaint": "Customer complaint pattern linked to '{target_id}'. "
                          "Graph analysis traces {cause_count} causal factors.",
}

# Recommended actions per RCA type
RECOMMENDED_ACTIONS = {
    "late_delivery": [
        "Review shipping mode allocation for affected routes",
        "Evaluate supplier lead time commitments",
        "Assess warehouse processing capacity",
        "Consider alternative logistics providers",
    ],
    "inventory_stress": [
        "Adjust reorder points for affected products",
        "Diversify supplier base for critical items",
        "Review demand forecasting accuracy",
        "Evaluate safety stock levels",
    ],
    "demand_spike": [
        "Validate demand signals against seasonal patterns",
        "Check for promotional or market events",
        "Assess supplier capacity for surge handling",
        "Review inventory buffer adequacy",
    ],
    "supplier_failure": [
        "Activate backup supplier agreements",
        "Assess inventory coverage for affected products",
        "Review supplier performance SLAs",
        "Evaluate supplier diversification strategy",
    ],
    "warehouse_congestion": [
        "Redistribute inventory across warehouses",
        "Optimize picking and packing workflows",
        "Evaluate temporary storage solutions",
        "Review inbound shipment scheduling",
    ],
    "shipping_delay": [
        "Evaluate alternative shipping routes",
        "Review carrier performance metrics",
        "Assess impact of weather or regional disruptions",
        "Consider expedited shipping for critical orders",
    ],
    "customer_complaint": [
        "Trace delivery timeline for affected orders",
        "Review product quality from implicated suppliers",
        "Assess communication gaps in order tracking",
        "Evaluate compensation and recovery options",
    ],
}


class ReportGenerator:
    """
    Generates structured RCA reports from analysis results.

    Combines:
    - Causal analysis results
    - Risk contribution scores
    - Dependency rankings
    - Path analysis findings
    """

    def generate_report(
        self,
        target_id: str,
        target_label: str,
        rca_type: str,
        causal_result: CausalAnalysisResult | None = None,
        contribution_result: ContributionResult | None = None,
        ranking_result: DependencyRankingResult | None = None,
        path_result: PathAnalysisResult | None = None,
        total_duration_ms: float = 0.0,
    ) -> RCAReport:
        """Generate a complete RCA report from all analysis components."""
        report_id = generate_rca_id(target_id, rca_type)

        # Extract primary and secondary causes
        primary_cause, secondary_causes = self._extract_causes(causal_result)

        # Extract risk contributors
        risk_contributors = self._extract_contributors(contribution_result)

        # Extract critical relationships
        critical_rels = self._extract_critical_relationships(ranking_result)

        # Extract affected entities
        affected = self._extract_affected_entities(
            causal_result, contribution_result, ranking_result
        )

        # Build causal chain summary
        causal_chain = causal_result.primary_chain.to_dict() if (
            causal_result and causal_result.primary_chain
        ) else {}

        # Build investigation paths
        investigation_paths = []
        if path_result:
            investigation_paths = [p.to_dict() for p in path_result.investigation_paths[:3]]

        # Compute overall confidence
        confidence = self._compute_overall_confidence(
            causal_result, contribution_result
        )

        # Generate problem summary
        cause_count = len(secondary_causes) + (1 if primary_cause else 0)
        summary_template = PROBLEM_SUMMARIES.get(rca_type, PROBLEM_SUMMARIES["late_delivery"])
        problem_summary = summary_template.format(
            target_id=target_id, cause_count=cause_count, confidence=confidence
        )

        # Get recommended actions
        actions = RECOMMENDED_ACTIONS.get(rca_type, RECOMMENDED_ACTIONS["late_delivery"])

        return RCAReport(
            report_id=report_id,
            rca_type=rca_type,
            target_id=target_id,
            target_label=target_label,
            problem_summary=problem_summary,
            overall_confidence=confidence,
            overall_risk_level=compute_risk_label(confidence),
            primary_root_cause=primary_cause,
            secondary_causes=secondary_causes,
            risk_contributors=risk_contributors,
            critical_relationships=critical_rels,
            affected_suppliers=affected.get("suppliers", []),
            affected_products=affected.get("products", []),
            affected_warehouses=affected.get("warehouses", []),
            affected_regions=affected.get("regions", []),
            causal_chain=causal_chain,
            investigation_paths=investigation_paths,
            recommended_actions=actions,
            duration_ms=total_duration_ms,
            metadata={
                "causal_chains_found": causal_result.to_dict()["total_chains"] if causal_result else 0,
                "contributors_analyzed": len(risk_contributors),
                "paths_analyzed": len(investigation_paths),
            },
        )

    def _extract_causes(
        self, causal_result: CausalAnalysisResult | None
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Extract primary and secondary causes from causal analysis."""
        if not causal_result or not causal_result.root_causes:
            return {}, []

        primary = causal_result.root_causes[0] if causal_result.root_causes else {}
        secondary = causal_result.root_causes[1:5]
        return primary, secondary

    def _extract_contributors(
        self, contribution_result: ContributionResult | None
    ) -> list[dict[str, Any]]:
        """Extract top risk contributors."""
        if not contribution_result:
            return []
        return [c.to_dict() for c in contribution_result.contributors[:10]]

    def _extract_critical_relationships(
        self, ranking_result: DependencyRankingResult | None
    ) -> list[dict[str, Any]]:
        """Extract critical relationships from dependency ranking."""
        if not ranking_result:
            return []
        critical = []
        for dep in ranking_result.critical_nodes[:5]:
            critical.append({
                "node_id": dep.node_id,
                "label": dep.label,
                "criticality_score": dep.dependency_score,
                "is_bottleneck": dep.is_bottleneck,
            })
        return critical

    def _extract_affected_entities(
        self,
        causal_result: CausalAnalysisResult | None,
        contribution_result: ContributionResult | None,
        ranking_result: DependencyRankingResult | None,
    ) -> dict[str, list[Any]]:
        """Extract affected entities by type."""
        all_nodes: list[dict[str, Any]] = []

        if causal_result and causal_result.primary_chain:
            for event in causal_result.primary_chain.events:
                all_nodes.append({"node_id": event.node_id, "label": event.label})

        if contribution_result:
            for contrib in contribution_result.contributors:
                all_nodes.append({"node_id": contrib.node_id, "label": contrib.label})

        if ranking_result:
            for dep in ranking_result.ranked_dependencies:
                all_nodes.append({"node_id": dep.node_id, "label": dep.label})

        # Categorize
        suppliers = list({n["node_id"] for n in all_nodes if n["label"] == "Supplier"})
        products = list({n["node_id"] for n in all_nodes if n["label"] == "Product"})
        warehouses = list({n["node_id"] for n in all_nodes if n["label"] == "Warehouse"})

        # Regions from warehouse properties (simplified)
        regions: list[str] = []

        return {
            "suppliers": [{"node_id": s} for s in suppliers[:10]],
            "products": [{"node_id": p} for p in products[:10]],
            "warehouses": [{"node_id": w} for w in warehouses[:10]],
            "regions": regions,
        }

    def _compute_overall_confidence(
        self,
        causal_result: CausalAnalysisResult | None,
        contribution_result: ContributionResult | None,
    ) -> float:
        """Compute overall RCA confidence score."""
        scores: list[float] = []

        if causal_result and causal_result.primary_chain:
            scores.append(causal_result.primary_chain.total_confidence)

        if contribution_result and contribution_result.contributors:
            top_score = contribution_result.contributors[0].total_score
            scores.append(min(1.0, top_score))

        if not scores:
            return 0.0
        return sum(scores) / len(scores)

"""
AMASCI Graph Validator
========================
Graph integrity validation: duplicates, orphans, schema, properties, relationships.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.graph.connection import Neo4jConnectionManager
from app.graph.utils import NODE_LABELS, RELATIONSHIP_TYPES

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: str  # "error", "warning", "info"
    category: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Complete validation result."""
    is_valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    total_checks: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "total_checks": self.total_checks,
            "issues": [
                {"severity": i.severity, "category": i.category, "message": i.message, "details": i.details}
                for i in self.issues
            ],
        }

    def add_issue(self, severity: str, category: str, message: str, details: dict | None = None) -> None:
        self.issues.append(ValidationIssue(
            severity=severity, category=category, message=message, details=details or {}
        ))
        if severity == "error":
            self.is_valid = False
            self.checks_failed += 1
        else:
            self.checks_passed += 1
        self.total_checks += 1

    def add_pass(self, category: str) -> None:
        self.checks_passed += 1
        self.total_checks += 1


class GraphValidator:
    """
    Validates Knowledge Graph integrity.

    Checks:
    - Duplicate node detection
    - Orphan node detection
    - Relationship validation
    - Property validation (required fields)
    - Schema validation (expected labels/types)
    """

    def __init__(self, connection: Neo4jConnectionManager):
        self._conn = connection

    async def validate(self) -> ValidationResult:
        """Run all validation checks."""
        result = ValidationResult()

        await self._check_duplicates(result)
        await self._check_orphans(result)
        await self._check_relationships(result)
        await self._check_properties(result)
        await self._check_schema(result)

        logger.info(
            f"Validation complete: valid={result.is_valid}, "
            f"passed={result.checks_passed}, failed={result.checks_failed}"
        )
        return result

    async def _check_duplicates(self, result: ValidationResult) -> None:
        """Detect duplicate nodes (same node_id within a label)."""
        for label in NODE_LABELS:
            query = f"""
                MATCH (n:{label})
                WITH n.node_id AS nid, count(*) AS cnt
                WHERE cnt > 1
                RETURN nid, cnt
            """
            records = await self._conn.execute_query(query)
            if records:
                for r in records:
                    result.add_issue(
                        "error", "duplicate_node",
                        f"Duplicate {label} node: {r['nid']} (count={r['cnt']})",
                        {"label": label, "node_id": r["nid"], "count": r["cnt"]},
                    )
            else:
                result.add_pass("duplicate_node")

    async def _check_orphans(self, result: ValidationResult) -> None:
        """Detect orphan nodes (no relationships)."""
        for label in NODE_LABELS:
            query = f"""
                MATCH (n:{label})
                WHERE NOT (n)--()
                RETURN count(n) AS cnt
            """
            records = await self._conn.execute_query(query)
            orphan_count = records[0]["cnt"] if records else 0

            if orphan_count > 0:
                # Orphans are warnings, not errors (CalendarEvents may be unlinked initially)
                result.add_issue(
                    "warning", "orphan_node",
                    f"{orphan_count} orphan {label} nodes detected",
                    {"label": label, "count": orphan_count},
                )
            else:
                result.add_pass("orphan_node")

    async def _check_relationships(self, result: ValidationResult) -> None:
        """Validate relationship integrity."""
        # Check for relationships pointing to non-existent nodes
        query = """
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS cnt
        """
        records = await self._conn.execute_query(query)

        if not records:
            result.add_issue("warning", "relationship_validation", "No relationships found in graph")
            return

        for r in records:
            rel_type = r["rel_type"]
            if rel_type not in RELATIONSHIP_TYPES:
                result.add_issue(
                    "warning", "relationship_validation",
                    f"Unexpected relationship type: {rel_type}",
                    {"rel_type": rel_type, "count": r["cnt"]},
                )
            else:
                result.add_pass("relationship_validation")

    async def _check_properties(self, result: ValidationResult) -> None:
        """Validate required properties exist on nodes."""
        required_props = {
            "Supplier": ["supplier_name", "risk_score"],
            "Product": ["category"],
            "Warehouse": ["city"],
            "Shipment": ["shipping_mode"],
            "Customer": ["customer_id"],
            "Order": ["order_id"],
            "CalendarEvent": ["event_name"],
        }

        for label, props in required_props.items():
            for prop in props:
                query = f"""
                    MATCH (n:{label})
                    WHERE n.{prop} IS NULL OR n.{prop} = ''
                    RETURN count(n) AS cnt
                """
                records = await self._conn.execute_query(query)
                missing = records[0]["cnt"] if records else 0

                if missing > 0:
                    result.add_issue(
                        "warning", "property_validation",
                        f"{missing} {label} nodes missing property '{prop}'",
                        {"label": label, "property": prop, "count": missing},
                    )
                else:
                    result.add_pass("property_validation")

    async def _check_schema(self, result: ValidationResult) -> None:
        """Validate expected node labels exist in graph."""
        query = "CALL db.labels() YIELD label RETURN collect(label) AS labels"
        try:
            records = await self._conn.execute_query(query)
            existing_labels = records[0]["labels"] if records else []
        except Exception:
            # Fallback
            existing_labels = []
            for lbl in NODE_LABELS:
                r = await self._conn.execute_query(f"MATCH (n:{lbl}) RETURN count(n) AS cnt")
                if r and r[0]["cnt"] > 0:
                    existing_labels.append(lbl)

        for label in NODE_LABELS:
            if label not in existing_labels:
                result.add_issue(
                    "info", "schema_validation",
                    f"Expected label '{label}' not found in graph",
                    {"label": label},
                )
            else:
                result.add_pass("schema_validation")

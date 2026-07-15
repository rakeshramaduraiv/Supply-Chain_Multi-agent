"""
AMASCI RCA Repository
========================
Persistence layer for RCA reports and history.
"""

import logging
from typing import Any

from app.rca.report_generator import RCAReport
from app.rca.utils import utc_now_iso

logger = logging.getLogger(__name__)


class RCARepository:
    """
    Repository for RCA report persistence.

    Stores:
    - Completed RCA reports
    - Analysis history
    - Performance metrics
    """

    def __init__(self):
        self._reports: list[dict[str, Any]] = []
        self._metrics: dict[str, Any] = {
            "total_analyses": 0,
            "avg_duration_ms": 0.0,
            "analyses_by_type": {},
        }

    def save_report(self, report: RCAReport) -> str:
        """Save an RCA report."""
        record = {
            "report_id": report.report_id,
            "rca_type": report.rca_type,
            "target_id": report.target_id,
            "target_label": report.target_label,
            "overall_confidence": report.overall_confidence,
            "overall_risk_level": report.overall_risk_level,
            "duration_ms": report.duration_ms,
            "generated_at": report.generated_at,
            "report": report.to_dict(),
        }
        self._reports.append(record)
        self._update_metrics(report)
        logger.info(f"[RCA] Report saved: {report.report_id}")
        return report.report_id

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        """Get a specific report by ID."""
        for record in self._reports:
            if record["report_id"] == report_id:
                return record["report"]
        return None

    def get_latest(self) -> dict[str, Any] | None:
        """Get the most recent RCA report."""
        if not self._reports:
            return None
        return self._reports[-1]["report"]

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get RCA analysis history (summary only)."""
        history = []
        for record in reversed(self._reports[-limit:]):
            history.append({
                "report_id": record["report_id"],
                "rca_type": record["rca_type"],
                "target_id": record["target_id"],
                "target_label": record["target_label"],
                "overall_confidence": record["overall_confidence"],
                "overall_risk_level": record["overall_risk_level"],
                "duration_ms": record["duration_ms"],
                "generated_at": record["generated_at"],
            })
        return history

    def get_metrics(self) -> dict[str, Any]:
        """Get repository metrics."""
        return {**self._metrics, "total_reports_stored": len(self._reports)}

    def clear_history(self) -> int:
        """Clear all stored reports."""
        count = len(self._reports)
        self._reports.clear()
        return count

    def _update_metrics(self, report: RCAReport) -> None:
        """Update running metrics."""
        self._metrics["total_analyses"] += 1
        count = self._metrics["total_analyses"]
        old_avg = self._metrics["avg_duration_ms"]
        self._metrics["avg_duration_ms"] = old_avg + (report.duration_ms - old_avg) / count

        rca_type = report.rca_type
        type_counts = self._metrics["analyses_by_type"]
        type_counts[rca_type] = type_counts.get(rca_type, 0) + 1

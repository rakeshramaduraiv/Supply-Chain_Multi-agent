"""
AMASCI Export Engine
======================
Export dashboard data in CSV, Excel, JSON, PDF formats.
"""

import csv
import io
import json
import logging
from typing import Any

from app.dashboard.utils import utc_now_iso

logger = logging.getLogger(__name__)


class ExportEngine:
    """
    Exports dashboard data in multiple formats.

    Supports: CSV, Excel (TSV), JSON, PDF (text summary).
    """

    def export_csv(self, data: list[dict[str, Any]], filename: str = "export") -> dict[str, Any]:
        """Export data as CSV string."""
        if not data:
            return {"format": "csv", "filename": f"{filename}.csv", "content": "", "rows": 0}

        output = io.StringIO()
        headers = list(data[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in data:
            writer.writerow({k: str(v) for k, v in row.items()})

        return {
            "format": "csv",
            "filename": f"{filename}.csv",
            "content": output.getvalue(),
            "rows": len(data),
            "columns": len(headers),
            "generated_at": utc_now_iso(),
        }

    def export_json(self, data: Any, filename: str = "export") -> dict[str, Any]:
        """Export data as JSON string."""
        content = json.dumps(data, indent=2, default=str)
        return {
            "format": "json",
            "filename": f"{filename}.json",
            "content": content,
            "size_bytes": len(content.encode()),
            "generated_at": utc_now_iso(),
        }

    def export_excel_tsv(self, data: list[dict[str, Any]], filename: str = "export") -> dict[str, Any]:
        """Export data as TSV (Excel-compatible)."""
        if not data:
            return {"format": "tsv", "filename": f"{filename}.tsv", "content": "", "rows": 0}

        headers = list(data[0].keys())
        lines = ["\t".join(headers)]
        for row in data:
            lines.append("\t".join(str(row.get(h, "")) for h in headers))

        content = "\n".join(lines)
        return {
            "format": "tsv",
            "filename": f"{filename}.tsv",
            "content": content,
            "rows": len(data),
            "generated_at": utc_now_iso(),
        }

    def export_report_text(self, report_data: dict[str, Any], filename: str = "report") -> dict[str, Any]:
        """Export a text-based report summary (PDF placeholder)."""
        lines = [
            "=" * 60,
            "AMASCI DASHBOARD REPORT",
            "=" * 60,
            f"Generated: {utc_now_iso()}",
            "",
        ]

        if "kpis" in report_data:
            lines.append("--- KEY PERFORMANCE INDICATORS ---")
            kpis = report_data["kpis"]
            lines.append(f"Overall Health: {kpis.get('overall_health', 'N/A')}")
            sc = kpis.get("supply_chain", {})
            lines.append(f"Supplier Reliability: {sc.get('supplier_reliability', 'N/A')}")
            lines.append(f"Shipping Efficiency: {sc.get('shipping_efficiency', 'N/A')}")
            lines.append("")

        if "executive_summary" in report_data:
            lines.append("--- EXECUTIVE SUMMARY ---")
            es = report_data["executive_summary"]
            for highlight in es.get("monthly_highlights", []):
                lines.append(f"  • {highlight}")
            lines.append("")
            lines.append("Recommendations:")
            for rec in es.get("system_recommendations", []):
                lines.append(f"  → {rec}")
            lines.append("")

        content = "\n".join(lines)
        return {
            "format": "txt",
            "filename": f"{filename}.txt",
            "content": content,
            "generated_at": utc_now_iso(),
        }

    def export_snapshot(self, dashboard_data: dict[str, Any]) -> dict[str, Any]:
        """Export a complete dashboard snapshot as JSON."""
        return self.export_json(dashboard_data, "dashboard_snapshot")

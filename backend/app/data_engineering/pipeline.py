"""
AMASCI Data Engineering Pipeline
===================================
Orchestrates the complete data engineering workflow:
Upload → Validate → Clean → Transform → Profile.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.data_engineering.cleaning import CleaningService, CleaningReport
from app.data_engineering.profiling import ProfilingService
from app.data_engineering.transformation import TransformationService, TransformationReport
from app.data_engineering.validation import ValidationService, ValidationReport

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete result of the data engineering pipeline."""

    dataset_id: str = ""
    status: str = "pending"
    started_at: str = ""
    completed_at: str = ""
    total_duration_ms: float = 0.0
    validation_report: dict[str, Any] = field(default_factory=dict)
    cleaning_report: dict[str, Any] = field(default_factory=dict)
    transformation_report: dict[str, Any] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    row_count_raw: int = 0
    row_count_clean: int = 0
    row_count_final: int = 0
    column_count_final: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "row_count_raw": self.row_count_raw,
            "row_count_clean": self.row_count_clean,
            "row_count_final": self.row_count_final,
            "column_count_final": self.column_count_final,
            "validation": self.validation_report,
            "cleaning": self.cleaning_report,
            "transformation": self.transformation_report,
            "profile": self.profile,
            "errors": self.errors,
        }


class DataEngineeringPipeline:
    """
    Orchestrates the complete data engineering workflow.

    Execution order:
    1. Validation → produces ValidationReport
    2. Cleaning → produces CleaningReport + cleaned DataFrame
    3. Transformation → produces TransformationReport + transformed DataFrame
    4. Profiling → produces dataset profile
    """

    def __init__(self) -> None:
        self.validator = ValidationService()
        self.cleaner = CleaningService()
        self.transformer = TransformationService()
        self.profiler = ProfilingService()

    def execute(self, df: pd.DataFrame, dataset_id: str) -> tuple[pd.DataFrame, PipelineResult]:
        """
        Execute the full data engineering pipeline.

        Returns the processed DataFrame and a complete pipeline result.
        """
        result = PipelineResult(
            dataset_id=dataset_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            row_count_raw=len(df),
        )
        pipeline_start = time.perf_counter()

        try:
            # Step 1: Validation
            logger.info(f"[{dataset_id}] Step 1/4: Validation")
            step_start = time.perf_counter()
            validation_report = self.validator.validate(df)
            result.validation_report = validation_report.to_dict()

            if not validation_report.is_valid:
                result.status = "failed"
                result.errors.append("Validation failed")
                result.completed_at = datetime.now(timezone.utc).isoformat()
                result.total_duration_ms = (time.perf_counter() - pipeline_start) * 1000
                return df, result

            logger.info(
                f"[{dataset_id}] Validation passed (score={validation_report.quality_score:.2f})",
                extra={"duration_ms": (time.perf_counter() - step_start) * 1000},
            )

            # Step 2: Cleaning
            logger.info(f"[{dataset_id}] Step 2/4: Cleaning")
            step_start = time.perf_counter()
            df_clean, cleaning_report = self.cleaner.clean(df)
            result.cleaning_report = cleaning_report.to_dict()
            result.row_count_clean = len(df_clean)

            logger.info(
                f"[{dataset_id}] Cleaning complete ({cleaning_report.rows_before}→{cleaning_report.rows_after})",
                extra={"duration_ms": (time.perf_counter() - step_start) * 1000},
            )

            # Step 3: Transformation
            logger.info(f"[{dataset_id}] Step 3/4: Transformation")
            step_start = time.perf_counter()
            df_transformed, transform_report = self.transformer.transform(df_clean)
            result.transformation_report = transform_report.to_dict()

            logger.info(
                f"[{dataset_id}] Transformation complete ({len(transform_report.columns_added)} cols added)",
                extra={"duration_ms": (time.perf_counter() - step_start) * 1000},
            )

            # Step 4: Profiling
            logger.info(f"[{dataset_id}] Step 4/4: Profiling")
            step_start = time.perf_counter()
            profile = self.profiler.generate_profile(df_transformed)
            result.profile = profile

            logger.info(
                f"[{dataset_id}] Profiling complete",
                extra={"duration_ms": (time.perf_counter() - step_start) * 1000},
            )

            # Finalize
            result.status = "completed"
            result.row_count_final = len(df_transformed)
            result.column_count_final = len(df_transformed.columns)

        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))
            logger.error(f"[{dataset_id}] Pipeline failed: {e}", exc_info=True)
            df_transformed = df

        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.total_duration_ms = (time.perf_counter() - pipeline_start) * 1000

        logger.info(
            f"[{dataset_id}] Pipeline {result.status} in {result.total_duration_ms:.0f}ms",
            extra={
                "status": result.status,
                "duration_ms": result.total_duration_ms,
                "rows_final": result.row_count_final,
            },
        )

        return df_transformed, result

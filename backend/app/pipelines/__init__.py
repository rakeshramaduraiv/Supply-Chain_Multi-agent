"""
AMASCI Base Pipeline
=====================
Abstract pipeline with step sequencing, progress tracking, and error handling.
"""

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.enums import PipelineStatus


@dataclass
class PipelineStepResult:
    """Result of a single pipeline step."""

    step_name: str
    status: PipelineStatus
    duration_ms: float = 0.0
    output: Any = None
    error: str | None = None


@dataclass
class PipelineRunResult:
    """Result of a complete pipeline execution."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_duration_ms: float = 0.0
    steps_completed: list[PipelineStepResult] = field(default_factory=list)
    current_step: str | None = None
    progress_percent: float = 0.0
    errors: list[str] = field(default_factory=list)


class BasePipeline(ABC):
    """
    Abstract base for all AMASCI pipelines.

    Provides:
    - Step registration and sequencing
    - Progress tracking
    - Per-step timing
    - Error handling with rollback support
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._steps: list[str] = []
        self._result: PipelineRunResult = PipelineRunResult()

    @abstractmethod
    def define_steps(self) -> list[str]:
        """Define the ordered list of pipeline steps."""
        ...

    @abstractmethod
    async def execute_step(self, step_name: str, context: dict[str, Any]) -> Any:
        """Execute a single pipeline step."""
        ...

    async def run(self, context: dict[str, Any] | None = None) -> PipelineRunResult:
        """Execute the full pipeline."""
        context = context or {}
        self._steps = self.define_steps()
        self._result = PipelineRunResult()
        self._result.status = PipelineStatus.RUNNING
        self._result.started_at = datetime.now(timezone.utc)

        total_steps = len(self._steps)
        pipeline_start = time.perf_counter()

        self.logger.info(
            f"Pipeline started: {self.__class__.__name__}",
            extra={"run_id": self._result.run_id, "steps": self._steps},
        )

        for idx, step_name in enumerate(self._steps):
            self._result.current_step = step_name
            self._result.progress_percent = (idx / total_steps) * 100

            step_start = time.perf_counter()
            try:
                output = await self.execute_step(step_name, context)
                duration_ms = (time.perf_counter() - step_start) * 1000

                step_result = PipelineStepResult(
                    step_name=step_name,
                    status=PipelineStatus.COMPLETED,
                    duration_ms=round(duration_ms, 2),
                    output=output,
                )
                self._result.steps_completed.append(step_result)
                context[f"{step_name}_output"] = output

                self.logger.info(
                    f"Step completed: {step_name}",
                    extra={"duration_ms": round(duration_ms, 2)},
                )

            except Exception as e:
                duration_ms = (time.perf_counter() - step_start) * 1000
                error_msg = f"Step '{step_name}' failed: {str(e)}"

                step_result = PipelineStepResult(
                    step_name=step_name,
                    status=PipelineStatus.FAILED,
                    duration_ms=round(duration_ms, 2),
                    error=str(e),
                )
                self._result.steps_completed.append(step_result)
                self._result.errors.append(error_msg)
                self._result.status = PipelineStatus.FAILED

                self.logger.error(error_msg, exc_info=True)
                break

        if self._result.status != PipelineStatus.FAILED:
            self._result.status = PipelineStatus.COMPLETED
            self._result.progress_percent = 100.0

        self._result.completed_at = datetime.now(timezone.utc)
        self._result.total_duration_ms = round(
            (time.perf_counter() - pipeline_start) * 1000, 2
        )
        self._result.current_step = None

        self.logger.info(
            f"Pipeline {self._result.status.value}: {self.__class__.__name__}",
            extra={
                "run_id": self._result.run_id,
                "total_duration_ms": self._result.total_duration_ms,
                "steps_completed": len(self._result.steps_completed),
            },
        )

        return self._result

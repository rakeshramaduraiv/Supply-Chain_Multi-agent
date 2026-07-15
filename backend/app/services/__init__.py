"""
AMASCI Base Service
====================
Abstract base service providing logging, timing, and error handling.
"""

import logging
import time
from abc import ABC
from typing import Any


class BaseService(ABC):
    """
    Abstract base for all AMASCI services.

    Provides:
    - Structured logging
    - Execution timing
    - Standard error handling pattern
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._timings: dict[str, float] = {}

    def _start_timer(self, operation: str) -> float:
        """Start timing an operation."""
        start = time.perf_counter()
        self._timings[operation] = start
        return start

    def _end_timer(self, operation: str) -> float:
        """End timing and return duration in milliseconds."""
        start = self._timings.pop(operation, time.perf_counter())
        duration_ms = (time.perf_counter() - start) * 1000
        self.logger.info(
            f"{operation} completed",
            extra={"duration_ms": round(duration_ms, 2)},
        )
        return duration_ms

    def _log_start(self, operation: str, **context: Any) -> None:
        """Log the start of an operation."""
        self.logger.info(f"Starting: {operation}", extra=context)

    def _log_success(self, operation: str, **context: Any) -> None:
        """Log successful completion."""
        self.logger.info(f"Completed: {operation}", extra=context)

    def _log_error(self, operation: str, error: Exception, **context: Any) -> None:
        """Log an error."""
        self.logger.error(
            f"Failed: {operation} - {error}",
            extra=context,
            exc_info=True,
        )

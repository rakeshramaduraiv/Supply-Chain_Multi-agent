"""
AMASCI Utilities
=================
Shared utility functions: timing, validation, conversion, math.
"""

import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def timed(func: Callable) -> Callable:
    """Decorator to measure and log function execution time."""

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"{func.__qualname__} completed in {duration_ms:.2f}ms",
            extra={"duration_ms": round(duration_ms, 2)},
        )
        return result

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"{func.__qualname__} completed in {duration_ms:.2f}ms",
            extra={"duration_ms": round(duration_ms, 2)},
        )
        return result

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper

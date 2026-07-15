"""
AMASCI Logging System
======================
Structured JSON logging with rotation, daily files, and context injection.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

from app.core.config import get_settings


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "details"):
            log_entry["details"] = record.details

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for development console."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging() -> None:
    """Configure application-wide logging."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    log_path = Path(settings.log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    if settings.is_development:
        console_formatter = ConsoleFormatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        console_formatter = StructuredFormatter()
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # --- File Handler (Rotating by size) ---
    file_handler = RotatingFileHandler(
        filename=log_path / "amasci.log",
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(file_handler)

    # --- Daily Rotation Handler ---
    daily_handler = TimedRotatingFileHandler(
        filename=log_path / "amasci_daily.log",
        when="midnight",
        interval=1,
        backupCount=settings.log_retention_days,
        encoding="utf-8",
    )
    daily_handler.setLevel(log_level)
    daily_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(daily_handler)

    # --- Error-only Handler ---
    error_handler = RotatingFileHandler(
        filename=log_path / "amasci_errors.log",
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(error_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)

    logging.info("Logging system initialized", extra={"log_level": settings.log_level})

"""
AMASCI System Initialization Models
======================================
Database models for tracking system initialization state,
dataset metadata, and training history.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SystemState(Base, UUIDMixin, TimestampMixin):
    """
    Singleton record tracking whether the system has been initialized.
    Only one row should ever exist (id='system').
    """

    __tablename__ = "system_state"

    is_initialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initialized_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dataset_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dataset_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_columns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initialization_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    models_trained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    graph_nodes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    graph_relationships: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_retrain_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class InitializationLog(Base, UUIDMixin, TimestampMixin):
    """
    Audit log for every initialization or retraining attempt.
    """

    __tablename__ = "initialization_log"

    action: Mapped[str] = mapped_column(String(50), nullable=False)  # 'initialize' | 'retrain'
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'started' | 'completed' | 'failed'
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    dataset_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    step_completed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DatasetRecord(Base, UUIDMixin, TimestampMixin):
    """
    Record of every dataset processed by the system.
    """

    __tablename__ = "dataset_records"

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'master' | 'monthly' | 'actuals'
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    processing_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

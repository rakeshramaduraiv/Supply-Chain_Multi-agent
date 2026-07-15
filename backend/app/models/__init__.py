"""
AMASCI Database Models
=======================
SQLAlchemy ORM models for all domain entities.
"""

from app.models.base import Base, TimestampMixin, SoftDeleteMixin, UUIDMixin
from app.models.initialization import SystemState, InitializationLog, DatasetRecord
from app.models.domain import (
    Role,
    User,
    Dataset,
    FeatureRegistry,
    TrainedModel,
    ForecastRun,
    ForecastResult,
    ActualUpload,
    TPKELog,
    GraphVersion,
    SystemConfiguration,
    AuditLog,
    Notification,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    "UUIDMixin",
    "SystemState",
    "InitializationLog",
    "DatasetRecord",
    "Role",
    "User",
    "Dataset",
    "FeatureRegistry",
    "TrainedModel",
    "ForecastRun",
    "ForecastResult",
    "ActualUpload",
    "TPKELog",
    "GraphVersion",
    "SystemConfiguration",
    "AuditLog",
    "Notification",
]

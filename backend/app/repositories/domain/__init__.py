"""
AMASCI Domain Repositories
============================
Concrete repository implementations for all domain entities.
"""

from app.repositories.domain.user_repository import UserRepository
from app.repositories.domain.role_repository import RoleRepository
from app.repositories.domain.dataset_repository import DatasetRepository
from app.repositories.domain.feature_repository import FeatureRepository
from app.repositories.domain.model_repository import TrainedModelRepository
from app.repositories.domain.forecast_repository import ForecastRunRepository, ForecastResultRepository
from app.repositories.domain.actual_repository import ActualUploadRepository
from app.repositories.domain.tpke_repository import TPKELogRepository
from app.repositories.domain.graph_repository import GraphVersionRepository
from app.repositories.domain.config_repository import SystemConfigRepository
from app.repositories.domain.audit_repository import AuditLogRepository
from app.repositories.domain.notification_repository import NotificationRepository

__all__ = [
    "UserRepository",
    "RoleRepository",
    "DatasetRepository",
    "FeatureRepository",
    "TrainedModelRepository",
    "ForecastRunRepository",
    "ForecastResultRepository",
    "ActualUploadRepository",
    "TPKELogRepository",
    "GraphVersionRepository",
    "SystemConfigRepository",
    "AuditLogRepository",
    "NotificationRepository",
]

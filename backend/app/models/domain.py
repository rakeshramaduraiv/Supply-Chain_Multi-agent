"""
AMASCI Domain Models
=====================
Complete PostgreSQL schema for the supply chain intelligence platform.

Tables: users, roles, datasets, feature_registry, trained_models,
        forecast_runs, forecast_results, actual_uploads, tpke_logs,
        graph_versions, system_configuration, audit_logs, notifications
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, SoftDeleteMixin, UUIDMixin


# ─────────────────────────────────────────────────────────────────────────────
# ROLES
# ─────────────────────────────────────────────────────────────────────────────

class Role(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="role", lazy="selectin")

    __table_args__ = (
        Index("ix_roles_name", "name"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────────────────────────────────────

class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role: Mapped["Role"] = relationship("Role", back_populates="users", lazy="selectin")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user", lazy="noload")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_username", "username"),
        Index("ix_users_role_id", "role_id"),
        Index("ix_users_is_active", "is_active"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# DATASETS
# ─────────────────────────────────────────────────────────────────────────────

class Dataset(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # historical, actuals, supplementary
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    profiling_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processing_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    forecast_runs: Mapped[list["ForecastRun"]] = relationship("ForecastRun", back_populates="dataset", lazy="noload")
    actual_uploads: Mapped[list["ActualUpload"]] = relationship("ActualUpload", back_populates="dataset", lazy="noload")

    __table_args__ = (
        Index("ix_datasets_type", "dataset_type"),
        Index("ix_datasets_status", "status"),
        Index("ix_datasets_uploaded_by", "uploaded_by"),
        CheckConstraint("file_size_bytes >= 0", name="ck_datasets_file_size_positive"),
        CheckConstraint("quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)", name="ck_datasets_quality_range"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class FeatureRegistry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "feature_registry"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_type: Mapped[str] = mapped_column(String(30), nullable=False)  # numeric, categorical, temporal, derived
    data_type: Mapped[str] = mapped_column(String(30), nullable=False)  # float, int, string, bool
    source_column: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transformation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    importance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    statistics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_feature_name_version"),
        Index("ix_feature_registry_name", "name"),
        Index("ix_feature_registry_type", "feature_type"),
        Index("ix_feature_registry_active", "is_active"),
        CheckConstraint("version >= 1", name="ck_feature_version_positive"),
        CheckConstraint("importance_score IS NULL OR (importance_score >= 0 AND importance_score <= 1)", name="ck_feature_importance_range"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# TRAINED MODELS
# ─────────────────────────────────────────────────────────────────────────────

class TrainedModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "trained_models"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)  # lightgbm, random_forest, xgboost
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="training")  # training, active, archived, failed
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    hyperparameters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feature_importance_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    training_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trained_by: Mapped[str | None] = mapped_column(String(255), nullable=True, default="system")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_name_version"),
        Index("ix_trained_models_name", "name"),
        Index("ix_trained_models_status", "status"),
        Index("ix_trained_models_active", "is_active"),
        Index("ix_trained_models_type", "model_type"),
        CheckConstraint("version >= 1", name="ck_model_version_positive"),
        CheckConstraint("accuracy IS NULL OR (accuracy >= 0 AND accuracy <= 1)", name="ck_model_accuracy_range"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# FORECAST RUNS
# ─────────────────────────────────────────────────────────────────────────────

class ForecastRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "forecast_runs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("trained_models.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending, running, completed, failed
    forecast_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    total_predictions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    parameters_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="forecast_runs", lazy="selectin")
    results: Mapped[list["ForecastResult"]] = relationship("ForecastResult", back_populates="forecast_run", lazy="noload", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_forecast_runs_status", "status"),
        Index("ix_forecast_runs_dataset_id", "dataset_id"),
        Index("ix_forecast_runs_model_id", "model_id"),
        Index("ix_forecast_runs_created_at", "created_at"),
        CheckConstraint("forecast_horizon_days > 0", name="ck_forecast_horizon_positive"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# FORECAST RESULTS
# ─────────────────────────────────────────────────────────────────────────────

class ForecastResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "forecast_results"

    forecast_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)  # product/region/supplier identifier
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # product, region, supplier
    forecast_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    forecast_run: Mapped["ForecastRun"] = relationship("ForecastRun", back_populates="results", lazy="selectin")

    __table_args__ = (
        Index("ix_forecast_results_run_id", "forecast_run_id"),
        Index("ix_forecast_results_entity", "entity_id", "entity_type"),
        Index("ix_forecast_results_date", "forecast_date"),
        Index("ix_forecast_results_risk", "risk_flag"),
        CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_forecast_confidence_range"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# ACTUAL UPLOADS
# ─────────────────────────────────────────────────────────────────────────────

class ActualUpload(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "actual_uploads"

    dataset_id: Mapped[str] = mapped_column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    forecast_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("forecast_runs.id", ondelete="SET NULL"), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mape: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    bias: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    comparison_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")  # uploaded, compared, validated
    uploaded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="actual_uploads", lazy="selectin")

    __table_args__ = (
        Index("ix_actual_uploads_dataset_id", "dataset_id"),
        Index("ix_actual_uploads_forecast_run_id", "forecast_run_id"),
        Index("ix_actual_uploads_period", "period_start", "period_end"),
        Index("ix_actual_uploads_status", "status"),
        CheckConstraint("period_end > period_start", name="ck_actual_period_valid"),
        CheckConstraint("accuracy_pct IS NULL OR (accuracy_pct >= 0 AND accuracy_pct <= 100)", name="ck_actual_accuracy_range"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# TPKE LOGS
# ─────────────────────────────────────────────────────────────────────────────

class TPKELog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tpke_logs"

    action: Mapped[str] = mapped_column(String(50), nullable=False)  # edge_created, edge_strengthened, edge_decayed, edge_removed
    source_node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    target_node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    graph_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("graph_versions.id", ondelete="SET NULL"), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")

    __table_args__ = (
        Index("ix_tpke_logs_action", "action"),
        Index("ix_tpke_logs_source", "source_node_id", "source_node_type"),
        Index("ix_tpke_logs_target", "target_node_id", "target_node_type"),
        Index("ix_tpke_logs_relationship", "relationship_type"),
        Index("ix_tpke_logs_created_at", "created_at"),
        CheckConstraint("confidence_after IS NULL OR (confidence_after >= 0 AND confidence_after <= 1)", name="ck_tpke_confidence_range"),
        CheckConstraint("frequency >= 1", name="ck_tpke_frequency_positive"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH VERSIONS
# ─────────────────────────────────────────────────────────────────────────────

class GraphVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "graph_versions"

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="building")  # building, active, archived
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationship_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    build_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_dataset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    tpke_mutations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    built_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")

    __table_args__ = (
        UniqueConstraint("version", name="uq_graph_version"),
        Index("ix_graph_versions_status", "status"),
        Index("ix_graph_versions_active", "is_active"),
        CheckConstraint("version >= 1", name="ck_graph_version_positive"),
        CheckConstraint("node_count >= 0", name="ck_graph_nodes_non_negative"),
        CheckConstraint("relationship_count >= 0", name="ck_graph_rels_non_negative"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

class SystemConfiguration(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "system_configuration"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="string")  # string, int, float, bool, json
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_system_config_key", "key"),
        Index("ix_system_config_category", "category"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGS
# ─────────────────────────────────────────────────────────────────────────────

class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)  # dataset, model, forecast, graph, config
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")  # success, failure

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_status", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, default="info")  # info, warning, error, success
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")  # low, normal, high, urgent
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="notifications", lazy="selectin")

    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_type", "notification_type"),
        Index("ix_notifications_priority", "priority"),
        Index("ix_notifications_created_at", "created_at"),
    )

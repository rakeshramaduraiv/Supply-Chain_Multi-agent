"""create core domain tables

Revision ID: 002_core_tables
Revises: 001_initialization
Create Date: 2024-12-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "002_core_tables"
down_revision = "001_initialization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── ROLES ────────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("permissions", JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_roles_name", "roles", ["name"])

    # ─── USERS ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role_id", "users", ["role_id"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # ─── DATASETS ─────────────────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("dataset_type", sa.String(50), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("schema_json", JSON(), nullable=True),
        sa.Column("profiling_json", JSON(), nullable=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("processing_duration_ms", sa.Float(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_datasets_type", "datasets", ["dataset_type"])
    op.create_index("ix_datasets_status", "datasets", ["status"])
    op.create_index("ix_datasets_uploaded_by", "datasets", ["uploaded_by"])
    op.create_check_constraint("ck_datasets_file_size_positive", "datasets", "file_size_bytes >= 0")
    op.create_check_constraint("ck_datasets_quality_range", "datasets", "quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 100)")

    # ─── FEATURE REGISTRY ─────────────────────────────────────────────────────
    op.create_table(
        "feature_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_type", sa.String(30), nullable=False),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("source_column", sa.String(100), nullable=True),
        sa.Column("transformation", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("importance_score", sa.Float(), nullable=True),
        sa.Column("statistics_json", JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_feature_name_version", "feature_registry", ["name", "version"])
    op.create_index("ix_feature_registry_name", "feature_registry", ["name"])
    op.create_index("ix_feature_registry_type", "feature_registry", ["feature_type"])
    op.create_index("ix_feature_registry_active", "feature_registry", ["is_active"])
    op.create_check_constraint("ck_feature_version_positive", "feature_registry", "version >= 1")
    op.create_check_constraint("ck_feature_importance_range", "feature_registry", "importance_score IS NULL OR (importance_score >= 0 AND importance_score <= 1)")

    # ─── TRAINED MODELS ───────────────────────────────────────────────────────
    op.create_table(
        "trained_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(30), nullable=False, server_default="training"),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("precision_score", sa.Float(), nullable=True),
        sa.Column("recall_score", sa.Float(), nullable=True),
        sa.Column("f1_score", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("hyperparameters_json", JSON(), nullable=True),
        sa.Column("feature_importance_json", JSON(), nullable=True),
        sa.Column("training_duration_ms", sa.Float(), nullable=True),
        sa.Column("training_rows", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("trained_by", sa.String(255), nullable=True, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_model_name_version", "trained_models", ["name", "version"])
    op.create_index("ix_trained_models_name", "trained_models", ["name"])
    op.create_index("ix_trained_models_status", "trained_models", ["status"])
    op.create_index("ix_trained_models_active", "trained_models", ["is_active"])
    op.create_index("ix_trained_models_type", "trained_models", ["model_type"])
    op.create_check_constraint("ck_model_version_positive", "trained_models", "version >= 1")
    op.create_check_constraint("ck_model_accuracy_range", "trained_models", "accuracy IS NULL OR (accuracy >= 0 AND accuracy <= 1)")

    # ─── GRAPH VERSIONS ───────────────────────────────────────────────────────
    op.create_table(
        "graph_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="building"),
        sa.Column("node_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relationship_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("build_duration_ms", sa.Float(), nullable=True),
        sa.Column("source_dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tpke_mutations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snapshot_path", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_json", JSON(), nullable=True),
        sa.Column("built_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_unique_constraint("uq_graph_version", "graph_versions", ["version"])
    op.create_index("ix_graph_versions_status", "graph_versions", ["status"])
    op.create_index("ix_graph_versions_active", "graph_versions", ["is_active"])
    op.create_check_constraint("ck_graph_version_positive", "graph_versions", "version >= 1")
    op.create_check_constraint("ck_graph_nodes_non_negative", "graph_versions", "node_count >= 0")
    op.create_check_constraint("ck_graph_rels_non_negative", "graph_versions", "relationship_count >= 0")

    # ─── FORECAST RUNS ────────────────────────────────────────────────────────
    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("trained_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("forecast_horizon_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("total_predictions", sa.Integer(), nullable=True),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("parameters_json", JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("triggered_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_forecast_runs_status", "forecast_runs", ["status"])
    op.create_index("ix_forecast_runs_dataset_id", "forecast_runs", ["dataset_id"])
    op.create_index("ix_forecast_runs_model_id", "forecast_runs", ["model_id"])
    op.create_index("ix_forecast_runs_created_at", "forecast_runs", ["created_at"])
    op.create_check_constraint("ck_forecast_horizon_positive", "forecast_runs", "forecast_horizon_days > 0")

    # ─── FORECAST RESULTS ─────────────────────────────────────────────────────
    op.create_table(
        "forecast_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("forecast_run_id", sa.String(36), sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("forecast_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_value", sa.Float(), nullable=False),
        sa.Column("confidence_lower", sa.Float(), nullable=True),
        sa.Column("confidence_upper", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("risk_flag", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_json", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_forecast_results_run_id", "forecast_results", ["forecast_run_id"])
    op.create_index("ix_forecast_results_entity", "forecast_results", ["entity_id", "entity_type"])
    op.create_index("ix_forecast_results_date", "forecast_results", ["forecast_date"])
    op.create_index("ix_forecast_results_risk", "forecast_results", ["risk_flag"])
    op.create_check_constraint("ck_forecast_confidence_range", "forecast_results", "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)")

    # ─── ACTUAL UPLOADS ───────────────────────────────────────────────────────
    op.create_table(
        "actual_uploads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forecast_run_id", sa.String(36), sa.ForeignKey("forecast_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_records", sa.Integer(), nullable=True),
        sa.Column("mape", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("bias", sa.Float(), nullable=True),
        sa.Column("accuracy_pct", sa.Float(), nullable=True),
        sa.Column("comparison_json", JSON(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_actual_uploads_dataset_id", "actual_uploads", ["dataset_id"])
    op.create_index("ix_actual_uploads_forecast_run_id", "actual_uploads", ["forecast_run_id"])
    op.create_index("ix_actual_uploads_period", "actual_uploads", ["period_start", "period_end"])
    op.create_index("ix_actual_uploads_status", "actual_uploads", ["status"])
    op.create_check_constraint("ck_actual_period_valid", "actual_uploads", "period_end > period_start")
    op.create_check_constraint("ck_actual_accuracy_range", "actual_uploads", "accuracy_pct IS NULL OR (accuracy_pct >= 0 AND accuracy_pct <= 100)")

    # ─── TPKE LOGS ────────────────────────────────────────────────────────────
    op.create_table(
        "tpke_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("source_node_id", sa.String(255), nullable=False),
        sa.Column("source_node_type", sa.String(50), nullable=False),
        sa.Column("target_node_id", sa.String(255), nullable=False),
        sa.Column("target_node_type", sa.String(50), nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("confidence_before", sa.Float(), nullable=True),
        sa.Column("confidence_after", sa.Float(), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evidence_json", JSON(), nullable=True),
        sa.Column("graph_version_id", sa.String(36), sa.ForeignKey("graph_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("triggered_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tpke_logs_action", "tpke_logs", ["action"])
    op.create_index("ix_tpke_logs_source", "tpke_logs", ["source_node_id", "source_node_type"])
    op.create_index("ix_tpke_logs_target", "tpke_logs", ["target_node_id", "target_node_type"])
    op.create_index("ix_tpke_logs_relationship", "tpke_logs", ["relationship_type"])
    op.create_index("ix_tpke_logs_created_at", "tpke_logs", ["created_at"])
    op.create_check_constraint("ck_tpke_confidence_range", "tpke_logs", "confidence_after IS NULL OR (confidence_after >= 0 AND confidence_after <= 1)")
    op.create_check_constraint("ck_tpke_frequency_positive", "tpke_logs", "frequency >= 1")

    # ─── SYSTEM CONFIGURATION ─────────────────────────────────────────────────
    op.create_table(
        "system_configuration",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_system_config_key", "system_configuration", ["key"])
    op.create_index("ix_system_config_category", "system_configuration", ["category"])

    # ─── AUDIT LOGS ───────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("details_json", JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_status", "audit_logs", ["status"])

    # ─── NOTIFICATIONS ────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False, server_default="info"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_type", "notifications", ["notification_type"])
    op.create_index("ix_notifications_priority", "notifications", ["priority"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    # ─── SEED DEFAULT ROLES ───────────────────────────────────────────────────
    op.execute("""
        INSERT INTO roles (id, name, description, permissions, is_active, created_at, updated_at)
        VALUES
            ('role-admin-0001', 'admin', 'Full system access', '{"all": true}', true, NOW(), NOW()),
            ('role-analyst-0002', 'analyst', 'Read/write access to analytics', '{"read": true, "write": true, "admin": false}', true, NOW(), NOW()),
            ('role-viewer-0003', 'viewer', 'Read-only access', '{"read": true, "write": false, "admin": false}', true, NOW(), NOW())
    """)


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("audit_logs")
    op.drop_table("system_configuration")
    op.drop_table("tpke_logs")
    op.drop_table("actual_uploads")
    op.drop_table("forecast_results")
    op.drop_table("forecast_runs")
    op.drop_table("graph_versions")
    op.drop_table("trained_models")
    op.drop_table("feature_registry")
    op.drop_table("datasets")
    op.drop_table("users")
    op.drop_table("roles")

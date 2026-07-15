"""create initialization tables

Revision ID: 001_initialization
Revises:
Create Date: 2024-12-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = "001_initialization"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # System State (singleton)
    op.create_table(
        "system_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("is_initialized", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("initialized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initialized_by", sa.String(255), nullable=True),
        sa.Column("dataset_filename", sa.String(500), nullable=True),
        sa.Column("dataset_rows", sa.Integer(), nullable=True),
        sa.Column("dataset_columns", sa.Integer(), nullable=True),
        sa.Column("initialization_duration_ms", sa.Float(), nullable=True),
        sa.Column("models_trained", sa.Integer(), nullable=True),
        sa.Column("graph_nodes", sa.Integer(), nullable=True),
        sa.Column("graph_relationships", sa.Integer(), nullable=True),
        sa.Column("last_retrain_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Initialization Log
    op.create_table(
        "initialization_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("triggered_by", sa.String(255), nullable=False),
        sa.Column("dataset_filename", sa.String(500), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("step_completed", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details_json", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Dataset Records
    op.create_table(
        "dataset_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("dataset_type", sa.String(50), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("column_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("processing_duration_ms", sa.Float(), nullable=True),
        sa.Column("metadata_json", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Indexes
    op.create_index("ix_initialization_log_action", "initialization_log", ["action"])
    op.create_index("ix_initialization_log_status", "initialization_log", ["status"])
    op.create_index("ix_dataset_records_type", "dataset_records", ["dataset_type"])
    op.create_index("ix_dataset_records_status", "dataset_records", ["status"])


def downgrade() -> None:
    op.drop_table("dataset_records")
    op.drop_table("initialization_log")
    op.drop_table("system_state")

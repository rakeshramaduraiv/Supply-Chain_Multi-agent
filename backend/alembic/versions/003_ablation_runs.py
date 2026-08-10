"""add ablation_runs table

Revision ID: 003_ablation_runs
Revises: 002_core_tables
Create Date: 2024-12-02
"""

from alembic import op
import sqlalchemy as sa

revision = "003_ablation_runs"
down_revision = "002_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ablation_runs",
        sa.Column("id",              sa.String(36),  primary_key=True),
        sa.Column("run_id",          sa.String(36),  nullable=False),
        sa.Column("arm",             sa.String(30),  nullable=False),   # with_graph | graph_ablated
        sa.Column("intelligence",    sa.String(30),  nullable=False),   # demand | supplier | logistics
        sa.Column("window_index",    sa.Integer(),   nullable=False),
        sa.Column("auc",             sa.Float(),     nullable=True),    # r2 for demand, roc_auc for classifiers
        sa.Column("f1",              sa.Float(),     nullable=True),
        sa.Column("precision_score", sa.Float(),     nullable=True),
        sa.Column("recall_score",    sa.Float(),     nullable=True),
        sa.Column("brier",           sa.Float(),     nullable=True),
        sa.Column("n_train",         sa.Integer(),   nullable=True),
        sa.Column("n_test",          sa.Integer(),   nullable=True),
        sa.Column("n_features",      sa.Integer(),   nullable=True),    # feature count for this arm
        sa.Column("seed",            sa.Integer(),   nullable=True),    # random_state used
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",      sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ablation_runs_run_id",       "ablation_runs", ["run_id"])
    op.create_index("ix_ablation_runs_intelligence", "ablation_runs", ["intelligence"])
    op.create_index("ix_ablation_runs_arm",          "ablation_runs", ["arm"])
    op.create_check_constraint(
        "ck_ablation_arm_valid", "ablation_runs",
        "arm IN ('with_graph', 'graph_ablated')"
    )
    op.create_check_constraint(
        "ck_ablation_intelligence_valid", "ablation_runs",
        "intelligence IN ('demand', 'supplier', 'logistics')"
    )
    op.create_check_constraint(
        "ck_ablation_n_features_positive", "ablation_runs",
        "n_features IS NULL OR n_features > 0"
    )


def downgrade() -> None:
    op.drop_table("ablation_runs")

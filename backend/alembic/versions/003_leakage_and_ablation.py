"""leakage_lineage_ablation_decision_params

Revision ID: 003_leakage_and_ablation
Revises: 002_core_tables
Create Date: 2025-01-01

Adds four tables required for academic publication:
  feature_lineage    — every feature declares when its value becomes knowable
  ablation_runs      — paired with/without-graph results (the results section)
  leakage_audits     — per-feature correlation and MI with verdicts
  decision_parameters — replaces hardcoded literals in decision_engine.py
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "003_leakage_and_ablation"
down_revision = "002_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── FEATURE LINEAGE ───────────────────────────────────────────────────────
    op.create_table(
        "feature_lineage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("feature_name", sa.String(128), unique=True, nullable=False),
        sa.Column("source_columns", JSON(), nullable=False),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("is_target_derived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("leak_check_passed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feature_lineage_name", "feature_lineage", ["feature_name"])
    op.create_index("ix_feature_lineage_availability", "feature_lineage", ["availability"])
    op.create_check_constraint(
        "ck_feature_availability",
        "feature_lineage",
        "availability IN ('ORDER_TIME', 'POST_DELIVERY')",
    )

    # ── ABLATION RUNS ─────────────────────────────────────────────────────────
    op.create_table(
        "ablation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False, index=True),
        sa.Column("arm", sa.String(32), nullable=False),
        sa.Column("intelligence", sa.String(32), nullable=False),
        sa.Column("window_index", sa.Integer(), nullable=False),
        sa.Column("auc", sa.Float(), nullable=True),
        sa.Column("f1", sa.Float(), nullable=True),
        sa.Column("precision_score", sa.Float(), nullable=True),
        sa.Column("recall_score", sa.Float(), nullable=True),
        sa.Column("brier", sa.Float(), nullable=True),
        sa.Column("n_train", sa.Integer(), nullable=True),
        sa.Column("n_test", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ablation_run_id", "ablation_runs", ["run_id"])
    op.create_index("ix_ablation_arm", "ablation_runs", ["arm"])
    op.create_index("ix_ablation_intelligence", "ablation_runs", ["intelligence"])
    op.create_check_constraint(
        "ck_ablation_arm",
        "ablation_runs",
        "arm IN ('with_graph', 'graph_ablated')",
    )

    # ── LEAKAGE AUDITS ────────────────────────────────────────────────────────
    op.create_table(
        "leakage_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_version_id", sa.String(64), nullable=False, index=True),
        sa.Column("feature_name", sa.String(128), nullable=False),
        sa.Column("target_corr", sa.Float(), nullable=True),
        sa.Column("mutual_info", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("threshold_used", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leakage_model_version", "leakage_audits", ["model_version_id"])
    op.create_index("ix_leakage_verdict", "leakage_audits", ["verdict"])
    op.create_check_constraint(
        "ck_leakage_verdict",
        "leakage_audits",
        "verdict IN ('PASS', 'SUSPECT', 'FAIL')",
    )

    # ── DECISION PARAMETERS ───────────────────────────────────────────────────
    op.create_table(
        "decision_parameters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(64), unique=True, nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        # source is mandatory and non-null — every cost figure must trace to a basis
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_decision_parameters_key", "decision_parameters", ["key"])

    # ── SEED DECISION PARAMETERS ──────────────────────────────────────────────
    # All values are assumptions for demonstration. Replace with actual cost data.
    # source column is mandatory — every figure must state its basis.
    op.execute("""
        INSERT INTO decision_parameters (id, key, value, unit, source, created_at, updated_at)
        VALUES
        ('dp-001', 'supplier_risk_threshold',       0.25,   'probability',
         'Assumed: industry rule-of-thumb for supplier reallocation trigger', NOW(), NOW()),
        ('dp-002', 'reallocation_pct_to_backup',   35.0,   'percent',
         'Assumed for demonstration: 35% backup allocation reduces single-supplier dependency', NOW(), NOW()),
        ('dp-003', 'safety_stock_increase_pct',    15.0,   'percent',
         'Assumed for demonstration: 15% buffer above 30-day forecast', NOW(), NOW()),
        ('dp-004', 'implementation_cost_usd',     3200.0,  'USD',
         'Assumed for demonstration: estimated logistics coordination cost', NOW(), NOW()),
        ('dp-005', 'expected_savings_usd',        14250.0, 'USD',
         'Assumed for demonstration: estimated savings from avoided late deliveries', NOW(), NOW()),
        ('dp-006', 'risk_reduction_pct',           18.5,   'percent',
         'Assumed for demonstration: estimated risk reduction from reallocation', NOW(), NOW()),
        ('dp-007', 'expected_sla_improvement_days', 1.8,   'days',
         'Assumed for demonstration: estimated SLA improvement from reallocation', NOW(), NOW()),
        ('dp-008', 'primary_supplier_pct',         65.0,   'percent',
         'Assumed for demonstration: primary supplier allocation after reallocation', NOW(), NOW()),
        ('dp-009', 'backup_supplier_pct',          35.0,   'percent',
         'Assumed for demonstration: backup supplier allocation after reallocation', NOW(), NOW())
    """)

    # ── SEED FEATURE LINEAGE ──────────────────────────────────────────────────
    op.execute("""
        INSERT INTO feature_lineage
            (id, feature_name, source_columns, availability, is_target_derived,
             leak_check_passed, rationale, created_at, updated_at)
        VALUES
        ('fl-001', 'supplier_hist_late_rate',
         '["Late_delivery_risk","Department Name","Shipping Mode"]',
         'ORDER_TIME', false, true,
         'Expanding shifted mean — row i sees only rows before it. No full-df encoding.', NOW(), NOW()),
        ('fl-002', 'route_hist_late_rate',
         '["Late_delivery_risk","Shipping Mode","Order Region"]',
         'ORDER_TIME', false, true,
         'Expanding shifted mean per (mode, region).', NOW(), NOW()),
        ('fl-003', 'region_hist_late_rate',
         '["Late_delivery_risk","Order Region"]',
         'ORDER_TIME', false, true,
         'Expanding shifted mean per region.', NOW(), NOW()),
        ('fl-004', 'shipmode_hist_late_rate',
         '["Late_delivery_risk","Shipping Mode"]',
         'ORDER_TIME', false, true,
         'Expanding shifted mean per shipping mode.', NOW(), NOW()),
        ('fl-005', 'is_delayed',
         '["Days for shipping (real)","Days for shipment (scheduled)"]',
         'POST_DELIVERY', true, false,
         'Equals Late_delivery_risk exactly. BANNED from all late-delivery models.', NOW(), NOW()),
        ('fl-006', 'delivery_gap',
         '["Days for shipping (real)","Days for shipment (scheduled)"]',
         'POST_DELIVERY', true, false,
         'real - sched. Monotone in target. BANNED from late-delivery models.', NOW(), NOW()),
        ('fl-007', 'shipping_delay_ratio',
         '["Days for shipping (real)","Days for shipment (scheduled)"]',
         'POST_DELIVERY', true, false,
         'real/sched. Monotone in target. BANNED from late-delivery models.', NOW(), NOW()),
        ('fl-008', 'days_scheduled',
         '["Days for shipment (scheduled)"]',
         'ORDER_TIME', false, true,
         'Scheduled shipping days — known at order placement. Safe to use.', NOW(), NOW()),
        ('fl-009', 'graph_avg_shipping_delay',
         '["Days for shipment (scheduled)","Shipping Mode","Order Region"]',
         'ORDER_TIME', false, true,
         'Per (mode, region) mean of scheduled days. Uses pre-shipment plan, not actual.', NOW(), NOW())
    """)


def downgrade() -> None:
    op.drop_table("decision_parameters")
    op.drop_table("leakage_audits")
    op.drop_table("ablation_runs")
    op.drop_table("feature_lineage")

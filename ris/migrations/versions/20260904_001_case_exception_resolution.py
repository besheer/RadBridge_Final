"""Case exception resolution mappings and audit events.

Revision ID: 20260904_001
Revises: 20260903_003
"""
from alembic import op
import sqlalchemy as sa


revision = "20260904_001"
down_revision = "20260903_003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "readiness_series_alias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("procedure_quality_rule.id"), nullable=False),
        sa.Column("source_alias", sa.String(255), nullable=False),
        sa.Column("alias_normalized", sa.String(255), nullable=False),
        sa.Column("canonical_series", sa.String(120), nullable=False),
        sa.Column("match_field", sa.String(20), nullable=False, server_default="EITHER"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("rule_id", "alias_normalized", "match_field", name="uq_readiness_series_alias_rule_value_field"),
    )
    op.create_index("ix_readiness_series_alias_rule", "readiness_series_alias", ["rule_id"])
    op.create_index("ix_readiness_series_alias_active", "readiness_series_alias", ["active"])

    op.create_table(
        "case_readiness_override",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("order.id"), nullable=False),
        sa.Column("blocker", sa.String(80), nullable=False),
        sa.Column("override_value", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deactivated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_case_readiness_override_order", "case_readiness_override", ["order_id"])
    op.create_index("ix_case_readiness_override_active", "case_readiness_override", ["active"])
    op.create_index("uq_case_readiness_override_one_active", "case_readiness_override", ["order_id", "blocker"], unique=True, postgresql_where=sa.text("active IS TRUE"))

    op.create_table(
        "case_exception_resolution_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("order.id"), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("blocker", sa.String(80), nullable=False, server_default=""),
        sa.Column("old_value", sa.String(500), nullable=False, server_default=""),
        sa.Column("new_value", sa.String(500), nullable=False, server_default=""),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_case_exception_resolution_event_order", "case_exception_resolution_event", ["order_id", "created_at"])
    op.create_index("ix_case_exception_resolution_event_action", "case_exception_resolution_event", ["action"])


def downgrade():
    op.drop_table("case_exception_resolution_event")
    op.drop_table("case_readiness_override")
    op.drop_table("readiness_series_alias")

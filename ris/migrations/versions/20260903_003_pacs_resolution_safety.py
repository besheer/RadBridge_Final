"""PACS resolution history and safe exam linking

Revision ID: 20260903_003
Revises: 20260903_002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260903_003"
down_revision = "20260903_002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pacs_study_match", sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pacs_study_match", sa.Column("superseded_at", sa.DateTime(), nullable=True))
    op.add_column("pacs_study_match", sa.Column("superseded_by", sa.Integer(), nullable=True))
    op.add_column("pacs_study_match", sa.Column("superseded_reason", sa.String(500), nullable=False, server_default=""))
    op.execute("""
        UPDATE pacs_study_match m
        SET is_current=TRUE
        FROM "order" o
        WHERE o.id=m.order_id
          AND NULLIF(o.pacs_study_id,'') IS NOT NULL
          AND m.orthanc_study_id=o.pacs_study_id
    """)
    op.execute("""
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM pacs_study_match
            WHERE is_current IS TRUE
            GROUP BY order_id HAVING COUNT(*) > 1
          ) THEN RAISE EXCEPTION 'MULTIPLE_CURRENT_PACS_MATCH_PREFLIGHT';
          END IF;
        END $$
    """)
    op.create_index("uq_pacs_match_one_current_per_order", "pacs_study_match", ["order_id"], unique=True, postgresql_where=sa.text("is_current IS TRUE"))

    op.create_table("pacs_exam_link",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("orthanc_study_id", sa.String(120), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("order.id"), nullable=False),
        sa.Column("link_role", sa.String(20), nullable=False, server_default="SECONDARY"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("removed_by", sa.Integer(), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pacs_exam_link_study", "pacs_exam_link", ["orthanc_study_id"])
    op.create_index("ix_pacs_exam_link_order", "pacs_exam_link", ["order_id"])
    op.create_index("uq_pacs_exam_link_active_pair", "pacs_exam_link", ["orthanc_study_id", "order_id"], unique=True, postgresql_where=sa.text("active IS TRUE"))

    op.create_table("pacs_resolution_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("order.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("old_orthanc_study_id", sa.String(120), nullable=False, server_default=""),
        sa.Column("new_orthanc_study_id", sa.String(120), nullable=False, server_default=""),
        sa.Column("old_study_instance_uid", sa.String(180), nullable=False, server_default=""),
        sa.Column("new_study_instance_uid", sa.String(180), nullable=False, server_default=""),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_pacs_resolution_event_order", "pacs_resolution_event", ["order_id", "created_at"])


def downgrade():
    op.drop_table("pacs_resolution_event")
    op.drop_table("pacs_exam_link")
    op.drop_index("uq_pacs_match_one_current_per_order", table_name="pacs_study_match")
    op.drop_column("pacs_study_match", "superseded_reason")
    op.drop_column("pacs_study_match", "superseded_by")
    op.drop_column("pacs_study_match", "superseded_at")
    op.drop_column("pacs_study_match", "is_current")

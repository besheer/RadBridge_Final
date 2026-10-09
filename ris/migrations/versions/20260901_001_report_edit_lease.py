"""report edit lease and typist role

Revision ID: 20260901_001
Revises: 20260821_001
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260901_001"
down_revision = "20260821_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_edit_lease",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("order.id"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            sa.Integer(),
            sa.ForeignKey("report.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id"),
            nullable=False,
        ),
        sa.Column(
            "editor_type",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "lease_token_hash",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "renewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "order_id",
            name="uq_report_edit_lease_order_id",
        ),
    )

    op.create_index(
        "ix_report_edit_lease_expires_at",
        "report_edit_lease",
        ["expires_at"],
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION radbridge_audit_append_only_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'AUDIT_LOG_APPEND_ONLY';
        END;
        $$;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS radbridge_audit_append_only
        ON audit_log
    """)

    op.execute("""
        CREATE TRIGGER radbridge_audit_append_only
        BEFORE UPDATE OR DELETE
        ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION radbridge_audit_append_only_guard()
    """)


    op.execute("""
        INSERT INTO role (
            code,
            name,
            permissions_json
        )
        SELECT
            'TYPIST',
            'Typist',
            '["dashboard.view","patients.view","orders.view","reports.view","reports.edit.draft","reports.version.view"]'
        WHERE NOT EXISTS (
            SELECT 1
            FROM role
            WHERE code = 'TYPIST'
        )
    """)


def downgrade():
    op.execute("""
        DROP TRIGGER IF EXISTS radbridge_audit_append_only
        ON audit_log
    """)

    op.execute("""
        DROP FUNCTION IF EXISTS radbridge_audit_append_only_guard()
    """)

    op.drop_index(
        "ix_report_edit_lease_expires_at",
        table_name="report_edit_lease",
    )
    op.drop_table("report_edit_lease")

    op.execute("""
        DELETE FROM role
        WHERE code = 'TYPIST'
          AND NOT EXISTS (
              SELECT 1
              FROM "user"
              WHERE "user".role_id = role.id
          )
    """)

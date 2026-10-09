"""report version unified safety metadata

Revision ID: 20260902_001
Revises: 20260901_001
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260902_001"
down_revision = "20260901_001"
branch_labels = None
depends_on = None


def upgrade():

    # Unified clinical report version safety metadata.
    #
    # status/editor_type are introduced with temporary server
    # defaults so existing rows can be safely backfilled while
    # preserving NOT NULL semantics.

    op.add_column(
        "report_version",
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="DRAFT",
        ),
    )

    op.add_column(
        "report_version",
        sa.Column(
            "editor_type",
            sa.String(length=30),
            nullable=False,
            server_default="UNKNOWN",
        ),
    )

    op.add_column(
        "report_version",
        sa.Column(
            "base_version_no",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "report_version",
        sa.Column(
            "commit_id",
            sa.String(length=36),
            nullable=True,
        ),
    )

    op.add_column(
        "report_version",
        sa.Column(
            "verified_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "report_version",
        sa.Column(
            "verified_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "report_version",
        sa.Column(
            "finalized_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "report_version",
        sa.Column(
            "finalized_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_report_version_verified_by_user_id",
        "report_version",
        "user",
        ["verified_by_user_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_report_version_finalized_by_user_id",
        "report_version",
        "user",
        ["finalized_by_user_id"],
        ["id"],
    )

    op.create_unique_constraint(
        "uq_report_version_report_version_no",
        "report_version",
        ["report_id", "version_no"],
    )

    # Match SQLAlchemy model semantics:
    # defaults are application-side, not permanent DB defaults.
    op.alter_column(
        "report_version",
        "status",
        server_default=None,
    )

    op.alter_column(
        "report_version",
        "editor_type",
        server_default=None,
    )


def downgrade():

    op.drop_constraint(
        "uq_report_version_report_version_no",
        "report_version",
        type_="unique",
    )

    op.drop_constraint(
        "fk_report_version_finalized_by_user_id",
        "report_version",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_report_version_verified_by_user_id",
        "report_version",
        type_="foreignkey",
    )

    op.drop_column("report_version", "finalized_at")
    op.drop_column("report_version", "finalized_by_user_id")
    op.drop_column("report_version", "verified_at")
    op.drop_column("report_version", "verified_by_user_id")
    op.drop_column("report_version", "commit_id")
    op.drop_column("report_version", "base_version_no")
    op.drop_column("report_version", "editor_type")
    op.drop_column("report_version", "status")

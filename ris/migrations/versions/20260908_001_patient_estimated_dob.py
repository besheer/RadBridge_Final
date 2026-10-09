"""Track whether a patient date of birth is approximate.

Revision ID: 20260908_001
Revises: 20260904_001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260908_001"
down_revision = "20260904_001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "patient",
        sa.Column(
            "dob_estimated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("patient", "dob_estimated")

"""persist case readiness series evidence

Revision ID: 20260903_002
Revises: 20260903_001
"""
from alembic import op
import sqlalchemy as sa

revision = "20260903_002"
down_revision = "20260903_001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("case_readiness", sa.Column("missing_series", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("case_readiness", sa.Column("series_evidence_json", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("case_readiness", sa.Column("facts_sha256", sa.String(64), nullable=False, server_default=""))
    op.add_column("case_readiness", sa.Column("series_checked_at", sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column("case_readiness", "series_checked_at")
    op.drop_column("case_readiness", "facts_sha256")
    op.drop_column("case_readiness", "series_evidence_json")
    op.drop_column("case_readiness", "missing_series")

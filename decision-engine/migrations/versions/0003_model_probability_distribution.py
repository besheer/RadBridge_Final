"""Persist validated provider probabilities for human review and evaluation."""
from alembic import op
import sqlalchemy as sa

revision = '0003_model_probabilities'
down_revision = '0002_jev_metadata'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('decisions', sa.Column('model_probabilities', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('decisions', 'model_probabilities')

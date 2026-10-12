"""Persist validated Jev suggestion metadata without raw provider payloads."""
from alembic import op
import sqlalchemy as sa

revision = '0002_jev_metadata'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('decisions', sa.Column('model_suggestion', sa.String(40), nullable=True))
    op.add_column('decisions', sa.Column('model_confidence', sa.Float(), nullable=True))
    op.add_column('decisions', sa.Column('model_name', sa.String(80), nullable=True))

def downgrade():
    op.drop_column('decisions', 'model_name')
    op.drop_column('decisions', 'model_confidence')
    op.drop_column('decisions', 'model_suggestion')

"""Initial isolated decision audit and human review schema."""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('decisions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('request_id', sa.String(80), nullable=False),
        sa.Column('task_code', sa.String(64), nullable=False),
        sa.Column('task_version', sa.String(32), nullable=False),
        sa.Column('branch_id', sa.String(80), nullable=False),
        sa.Column('actor_id', sa.String(80), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('evidence_sha256', sa.String(64), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('category', sa.String(40), nullable=False),
        sa.Column('suggested_action', sa.String(40), nullable=False),
        sa.Column('reason_code', sa.String(64), nullable=False),
        sa.Column('provider', sa.String(24), nullable=False),
        sa.Column('policy_version', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_by', sa.String(80)),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('review_outcome', sa.String(16)),
        sa.Column('review_reason', sa.String(1000)),
        sa.UniqueConstraint('branch_id','request_id',name='uq_decision_branch_request'))
    op.create_index('ix_decisions_branch_status_created','decisions',['branch_id','status','created_at'])
    op.create_table('decision_audit_events',
        sa.Column('id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('decision_id',sa.String(36),nullable=False),
        sa.Column('branch_id',sa.String(80),nullable=False),
        sa.Column('actor_id',sa.String(80),nullable=False),
        sa.Column('event_type',sa.String(32),nullable=False),
        sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('details',sa.JSON(),nullable=False),
        sa.ForeignKeyConstraint(['decision_id'],['decisions.id'],ondelete='RESTRICT'))
    op.create_index('ix_decision_audit_branch_time','decision_audit_events',['branch_id','occurred_at'])

def downgrade():
    op.drop_index('ix_decision_audit_branch_time',table_name='decision_audit_events')
    op.drop_table('decision_audit_events')
    op.drop_index('ix_decisions_branch_status_created',table_name='decisions')
    op.drop_table('decisions')

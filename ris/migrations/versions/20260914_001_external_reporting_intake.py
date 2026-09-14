"""Add isolated, administrator-controlled external reporting intake.

Revision ID: 20260914_001
Revises: 20260908_002
"""
from alembic import op
import sqlalchemy as sa

revision='20260914_001'
down_revision='20260908_002'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('external_reporting_setting',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('updated_by',sa.Integer(),sa.ForeignKey('user.id')),
        sa.Column('updated_at',sa.DateTime(),nullable=False))
    op.create_table('external_reporting_center',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('code',sa.String(40),nullable=False,unique=True),
        sa.Column('name',sa.String(160),nullable=False),
        sa.Column('ae_title',sa.String(80),nullable=False,unique=True),
        sa.Column('receiving_enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('assignment_enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('auto_queue',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('default_priority',sa.String(20),nullable=False,server_default='ROUTINE'),
        sa.Column('required_documents',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('created_by',sa.Integer(),sa.ForeignKey('user.id')),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('updated_at',sa.DateTime(),nullable=False))
    op.create_index('ix_external_reporting_center_code','external_reporting_center',['code'])
    op.create_index('ix_external_reporting_center_ae_title','external_reporting_center',['ae_title'])
    op.create_index('ix_external_reporting_center_active','external_reporting_center',['active'])
    op.create_table('external_center_doctor',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('center_id',sa.Integer(),sa.ForeignKey('external_reporting_center.id'),nullable=False),
        sa.Column('doctor_user_id',sa.Integer(),sa.ForeignKey('user.id'),nullable=False),
        sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.UniqueConstraint('center_id','doctor_user_id',name='uq_external_center_doctor'))
    op.create_index('ix_external_center_doctor_center_id','external_center_doctor',['center_id'])
    op.create_index('ix_external_center_doctor_doctor_user_id','external_center_doctor',['doctor_user_id'])
    op.create_index('ix_external_center_doctor_active','external_center_doctor',['active'])
    op.create_table('external_intake_case',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('center_id',sa.Integer(),sa.ForeignKey('external_reporting_center.id'),nullable=False),
        sa.Column('inbox_id',sa.Integer(),sa.ForeignKey('pacs_study_inbox.id'),nullable=False,unique=True),
        sa.Column('order_id',sa.Integer(),sa.ForeignKey('order.id'),unique=True),
        sa.Column('status',sa.String(30),nullable=False,server_default='RECEIVED'),
        sa.Column('review_note',sa.String(500),nullable=False,server_default=''),
        sa.Column('reviewed_by',sa.Integer(),sa.ForeignKey('user.id')),
        sa.Column('reviewed_at',sa.DateTime()),sa.Column('queued_at',sa.DateTime()),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    for name,column in [('center_id','center_id'),('inbox_id','inbox_id'),('order_id','order_id'),('status','status'),('created_at','created_at')]:
        op.create_index('ix_external_intake_case_'+name,'external_intake_case',[column])


def downgrade():
    op.drop_table('external_intake_case')
    op.drop_table('external_center_doctor')
    op.drop_table('external_reporting_center')
    op.drop_table('external_reporting_setting')

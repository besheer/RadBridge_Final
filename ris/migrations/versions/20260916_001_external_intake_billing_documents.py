"""Add per-center billing and pre-queue intake documents.

Revision ID: 20260916_001
Revises: 20260915_001
"""
from alembic import op
import sqlalchemy as sa

revision='20260916_001'
down_revision='20260915_001'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('external_reporting_center',
                  sa.Column('billing_enabled',sa.Boolean(),nullable=False,
                            server_default=sa.false()))
    op.add_column('external_reporting_center',
                  sa.Column('billing_contract_id',sa.Integer(),nullable=True))
    op.add_column('external_reporting_center',
                  sa.Column('default_report_fee',sa.Float(),nullable=False,
                            server_default='0'))
    op.create_foreign_key('fk_external_center_billing_contract',
                          'external_reporting_center','contract',
                          ['billing_contract_id'],['id'])
    op.create_index('ix_external_reporting_center_billing_contract_id',
                    'external_reporting_center',['billing_contract_id'])
    op.add_column('attachment',
                  sa.Column('external_intake_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_attachment_external_intake',
                          'attachment','external_intake_case',
                          ['external_intake_id'],['id'])
    op.create_index('ix_attachment_external_intake_id','attachment',
                    ['external_intake_id'])


def downgrade():
    op.drop_index('ix_attachment_external_intake_id',table_name='attachment')
    op.drop_constraint('fk_attachment_external_intake','attachment',type_='foreignkey')
    op.drop_column('attachment','external_intake_id')
    op.drop_index('ix_external_reporting_center_billing_contract_id',
                  table_name='external_reporting_center')
    op.drop_constraint('fk_external_center_billing_contract',
                       'external_reporting_center',type_='foreignkey')
    op.drop_column('external_reporting_center','default_report_fee')
    op.drop_column('external_reporting_center','billing_contract_id')
    op.drop_column('external_reporting_center','billing_enabled')

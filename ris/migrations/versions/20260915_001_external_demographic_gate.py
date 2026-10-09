"""Add fail-closed demographic verification to external intake.

Revision ID: 20260915_001
Revises: 20260914_001
"""
from alembic import op
import sqlalchemy as sa

revision='20260915_001'
down_revision='20260914_001'
branch_labels=None
depends_on=None


def upgrade():
    columns=(
        sa.Column('expected_patient_id',sa.String(80),nullable=False,server_default=''),
        sa.Column('expected_patient_name',sa.String(180),nullable=False,server_default=''),
        sa.Column('expected_dob',sa.String(8),nullable=False,server_default=''),
        sa.Column('expected_sex',sa.String(1),nullable=False,server_default=''),
        sa.Column('expected_accession',sa.String(120),nullable=False,server_default=''),
        sa.Column('dicom_patient_id',sa.String(80),nullable=False,server_default=''),
        sa.Column('dicom_patient_name',sa.String(180),nullable=False,server_default=''),
        sa.Column('dicom_dob',sa.String(8),nullable=False,server_default=''),
        sa.Column('dicom_sex',sa.String(1),nullable=False,server_default=''),
        sa.Column('dicom_accession',sa.String(120),nullable=False,server_default=''),
        sa.Column('demographic_status',sa.String(30),nullable=False,server_default='NOT_CHECKED'),
        sa.Column('demographic_score',sa.Float(),nullable=False,server_default='0'),
        sa.Column('demographic_checks_json',sa.Text(),nullable=False,server_default='[]'),
        sa.Column('demographic_facts_sha256',sa.String(64),nullable=False,server_default=''),
        sa.Column('demographic_verified_by',sa.Integer(),sa.ForeignKey('user.id')),
        sa.Column('demographic_verified_at',sa.DateTime()),
        sa.Column('demographic_override_approved',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('demographic_override_reason',sa.String(500),nullable=False,server_default=''),
        sa.Column('demographic_override_by',sa.Integer(),sa.ForeignKey('user.id')),
        sa.Column('demographic_override_at',sa.DateTime()),
        sa.Column('demographic_override_facts_sha256',sa.String(64),nullable=False,server_default=''),
    )
    for column in columns:
        op.add_column('external_intake_case',column)
    op.create_index('ix_external_intake_case_demographic_status',
                    'external_intake_case',['demographic_status'])


def downgrade():
    op.drop_index('ix_external_intake_case_demographic_status',
                  table_name='external_intake_case')
    for name in (
        'demographic_override_facts_sha256','demographic_override_at',
        'demographic_override_by','demographic_override_reason',
        'demographic_override_approved','demographic_verified_at',
        'demographic_verified_by','demographic_facts_sha256',
        'demographic_checks_json','demographic_score','demographic_status',
        'dicom_accession','dicom_sex','dicom_dob','dicom_patient_name',
        'dicom_patient_id','expected_accession','expected_sex','expected_dob',
        'expected_patient_name','expected_patient_id'
    ):
        op.drop_column('external_intake_case',name)

"""Additive FINAL correction schema. Originals and old versions are untouched.

Downgrading the running image is safe; these audit/content tables must be kept.
Deleting persisted correction history is deliberately not an automated downgrade.
"""
revision='20261007_001'
down_revision='20260916_001'
branch_labels=None
depends_on=None

def upgrade():
    from alembic import op
    import app as m
    for model in (m.ReportRevision,m.ReportRevisionVersion):
        model.__table__.create(bind=op.get_bind(),checkfirst=True)

def downgrade():
    raise RuntimeError('Retain report correction history; use application rollback without dropping clinical tables.')

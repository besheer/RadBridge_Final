"""Add immutable replacement payable adjustments; preserve original cash entries."""
revision = '20261008_001'
down_revision = '20261007_001'
branch_labels = None
depends_on = None


def upgrade():
    from alembic import op
    import app as m
    m.ReplacementSettlement.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Retain financial adjustment history; roll back the application without dropping this table.')

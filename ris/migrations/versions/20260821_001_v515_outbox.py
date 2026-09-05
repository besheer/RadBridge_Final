
"""v5.15 event outbox"""
from alembic import op
import sqlalchemy as sa

revision="20260821_001"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table(
        "event_outbox",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("event_type",sa.String(length=80),nullable=False),
        sa.Column("entity_type",sa.String(length=80),nullable=False,server_default=""),
        sa.Column("entity_id",sa.String(length=120),nullable=False,server_default=""),
        sa.Column("payload_json",sa.Text(),nullable=True),
        sa.Column("status",sa.String(length=20),nullable=True,server_default="PENDING"),
        sa.Column("attempts",sa.Integer(),nullable=True,server_default="0"),
        sa.Column("last_error",sa.Text(),nullable=True),
        sa.Column("created_at",sa.DateTime(),nullable=True),
        sa.Column("processed_at",sa.DateTime(),nullable=True),
    )
    op.create_index("ix_event_outbox_event_type","event_outbox",["event_type"])
    op.create_index("ix_event_outbox_status","event_outbox",["status"])
    op.create_index("ix_event_outbox_created_at","event_outbox",["created_at"])

def downgrade():
    op.drop_index("ix_event_outbox_created_at",table_name="event_outbox")
    op.drop_index("ix_event_outbox_status",table_name="event_outbox")
    op.drop_index("ix_event_outbox_event_type",table_name="event_outbox")
    op.drop_table("event_outbox")

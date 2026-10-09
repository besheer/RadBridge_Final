"""Link registered orders to calendar appointments.

Revision ID: 20260908_002
Revises: 20260908_001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260908_002"
down_revision = "20260908_001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("appointment") as batch:
        batch.add_column(sa.Column("order_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_appointment_order_id_order",
            "order",
            ["order_id"],
            ["id"],
        )
        batch.create_index(
            "uq_appointment_order_id",
            ["order_id"],
            unique=True,
        )

    if op.get_bind().dialect.name == "postgresql":
        # Link a pre-existing booking when it represents the same patient,
        # procedure, device and start time.  Rank protects the unique link if
        # legacy duplicate Orders happen to exist.
        op.execute(sa.text("""
            WITH candidates AS (
                SELECT
                    a.id AS appointment_id,
                    o.id AS order_id,
                    row_number() OVER (
                        PARTITION BY a.id
                        ORDER BY o.id DESC
                    ) AS appointment_rank,
                    row_number() OVER (
                        PARTITION BY o.id
                        ORDER BY a.id DESC
                    ) AS order_rank
                FROM appointment a
                JOIN "order" o
                  ON o.patient_id = a.patient_id
                 AND o.procedure_id = a.procedure_id
                 AND o.device_id = a.device_id
                 AND o.scheduled = a.scheduled
                WHERE a.order_id IS NULL
            )
            UPDATE appointment a
               SET order_id = c.order_id
              FROM candidates c
             WHERE a.id = c.appointment_id
               AND c.appointment_rank = 1
               AND c.order_rank = 1
               AND NOT EXISTS (
                   SELECT 1
                     FROM appointment linked
                    WHERE linked.order_id = c.order_id
               )
        """))

        # Registration historically created only Order rows.  Backfill only
        # complete schedulable rows that still have no linked Appointment.
        op.execute(sa.text("""
            INSERT INTO appointment (
                patient_id,
                branch_id,
                procedure_id,
                device_id,
                order_id,
                scheduled,
                status,
                source,
                notes,
                created_by,
                created_at,
                duration_min,
                priority,
                waiting_list
            )
            SELECT
                o.patient_id,
                o.branch_id,
                o.procedure_id,
                o.device_id,
                o.id,
                o.scheduled,
                CASE
                    WHEN upper(coalesce(o.status,'')) IN (
                        'REGISTERED','SCHEDULED','ARRIVED','IN_PROGRESS',
                        'EXAM_COMPLETED','REPORTING','VERIFIED','FINAL'
                    ) THEN upper(o.status)
                    ELSE 'REGISTERED'
                END,
                'ORDER_BACKFILL',
                '',
                o.created_by,
                coalesce(o.created_at,now()),
                greatest(5,coalesce(p.duration_min,20)),
                coalesce(o.priority,'ROUTINE'),
                false
            FROM "order" o
            JOIN procedure p ON p.id = o.procedure_id
            WHERE o.patient_id IS NOT NULL
              AND o.branch_id IS NOT NULL
              AND o.procedure_id IS NOT NULL
              AND o.device_id IS NOT NULL
              AND o.scheduled IS NOT NULL
              AND upper(coalesce(o.status,'')) NOT IN ('CANCELLED','NO_SHOW')
              AND NOT EXISTS (
                  SELECT 1
                    FROM appointment a
                   WHERE a.order_id = o.id
              )
        """))


def downgrade():
    with op.batch_alter_table("appointment") as batch:
        batch.drop_index("uq_appointment_order_id")
        batch.drop_constraint(
            "fk_appointment_order_id_order",
            type_="foreignkey",
        )
        batch.drop_column("order_id")

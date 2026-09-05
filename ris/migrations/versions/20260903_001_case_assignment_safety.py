"""case assignment concurrency safety

Revision ID: 20260903_001
Revises: 20260902_001
Create Date: 2026-09-03
"""

from alembic import op


revision = "20260903_001"
down_revision = "20260902_001"
branch_labels = None
depends_on = None


def upgrade():
    # Stop instead of guessing if historical corruption exists.  The reviewed
    # R8 baseline currently has zero duplicate active orders.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM case_assignment
                WHERE active IS TRUE
                GROUP BY order_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'CASE_ASSIGNMENT_DUPLICATE_ACTIVE_PREFLIGHT';
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_case_assignment_one_active_per_order
        ON case_assignment (order_id)
        WHERE active IS TRUE
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_case_assignment_one_active_per_order")

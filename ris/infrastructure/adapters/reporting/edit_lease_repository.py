"""SQL lease operations with caller-owned transactions and original lock order."""
from sqlalchemy import text


class SqlAlchemyEditLeaseRepository:
    def __init__(self, session):
        self.session = session

    def read_lease(self, order_id):
        return self.session.execute(text('\n            SELECT\n                order_id,\n                user_id,\n                editor_type,\n                lease_token_hash,\n                expires_at\n            FROM report_edit_lease\n            WHERE order_id = :order_id\n        '), {'order_id': int(order_id)}).mappings().first()

    def lock_order_owner(self, order_id):
        self.session.execute(text('SELECT id FROM "order" WHERE id = :id FOR UPDATE'), {'id': int(order_id)})
        return self.session.execute(text('SELECT assigned_doctor_id FROM "order" WHERE id = :id'), {'id': int(order_id)}).scalar()

    def lock_report(self, report_id):
        self.session.execute(text('\n            SELECT id\n            FROM report\n            WHERE id = :report_id\n            FOR UPDATE\n        '), {'report_id': int(report_id)})

    def read_locked_lease(self, order_id):
        return self.session.execute(text('\n            SELECT\n                user_id,\n                lease_token_hash,\n                expires_at\n            FROM report_edit_lease\n            WHERE order_id = :order_id\n            FOR UPDATE\n        '), {'order_id': int(order_id)}).mappings().first()

    def upsert(self, values):
        self.session.execute(text('\n            INSERT INTO report_edit_lease (\n                order_id,\n                report_id,\n                user_id,\n                editor_type,\n                lease_token_hash,\n                acquired_at,\n                renewed_at,\n                expires_at\n            )\n            VALUES (\n                :order_id,\n                :report_id,\n                :user_id,\n                :editor_type,\n                :lease_token_hash,\n                :now,\n                :now,\n                :expires\n            )\n            ON CONFLICT (order_id)\n            DO UPDATE SET\n                report_id = EXCLUDED.report_id,\n                user_id = EXCLUDED.user_id,\n                editor_type = EXCLUDED.editor_type,\n                lease_token_hash = EXCLUDED.lease_token_hash,\n                renewed_at = EXCLUDED.renewed_at,\n                expires_at = EXCLUDED.expires_at\n        '), values)

    def release(self, order_id, user_id=None, token_hash=None):
        sql = 'DELETE FROM report_edit_lease WHERE order_id = :order_id'
        params = {'order_id': int(order_id)}
        if user_id is not None:
            sql += ' AND user_id = :user_id'
            params['user_id'] = int(user_id)
        if token_hash is not None:
            sql += ' AND lease_token_hash = :lease_token_hash'
            params['lease_token_hash'] = token_hash
        return int(self.session.execute(text(sql), params).rowcount or 0)

    def clear_expired(self, now):
        return int(self.session.execute(text('DELETE FROM report_edit_lease WHERE expires_at <= :now'), {'now': now}).rowcount or 0)

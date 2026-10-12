"""Readiness scheduler persistence, transaction and PostgreSQL lock owner."""
from sqlalchemy import or_, text
from domain.readiness_schedule import CLOSED


class RunLease:
    def __init__(self, connection=None, acquired=True):
        self.connection, self.acquired = connection, acquired

    def release(self):
        if self.connection:
            self.connection.execute(text('SELECT pg_advisory_unlock(20261004, 411)'))
            self.connection.close()


class SqlAlchemyReadinessScheduleRepository:
    def __init__(self, session, engine_factory, Order, Report, CaseReadiness, AuditLog):
        self.session, self.engine_factory = session, engine_factory
        self.Order, self.Report, self.Readiness, self.AuditLog = Order, Report, CaseReadiness, AuditLog

    def acquire_run_lock(self):
        engine = self.engine_factory()
        if engine.dialect.name != 'postgresql':
            return RunLease()
        connection = engine.connect()
        acquired = connection.execute(text('SELECT pg_try_advisory_lock(20261004, 411)')).scalar()
        if not acquired:
            connection.close()
            return RunLease(acquired=False)
        return RunLease(connection)

    def candidate_ids(self):
        O, R, C = self.Order, self.Report, self.Readiness
        rows = (self.session.query(O).outerjoin(C, C.order_id==O.id)
                .filter(O.status.notin_(CLOSED), ~O.report.has(R.status.in_(CLOSED)),
                        or_(O.exam_status.in_(['EXAM_COMPLETED','REPORTING']),
                            O.status.in_(['IMAGES_RECEIVED','EXAM_COMPLETED','REPORTING'])))
                .order_by(C.checked_at.asc().nullsfirst(), O.id).limit(500).all())
        return [o.id for o in rows]

    def lock_order(self, oid):
        return self.session.query(self.Order).filter_by(id=oid).with_for_update(skip_locked=True).first()

    def lock_report(self, oid):
        return self.session.query(self.Report).filter_by(order_id=oid).with_for_update(skip_locked=True).first()

    def report_exists(self, oid):
        return self.session.query(self.Report).filter_by(order_id=oid).first() is not None

    def readiness(self, oid):
        return self.session.query(self.Readiness).filter_by(order_id=oid).first()

    def record_automatic_audit(self, oid, payload):
        self.session.add(self.AuditLog(action='CASE_READINESS_AUTO_RECHECKED', entity='order',
            entity_id=str(oid), username='readiness-maintenance', details=payload))

    def commit(self): self.session.commit()
    def rollback(self): self.session.rollback()

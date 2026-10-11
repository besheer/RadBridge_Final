"""Immutable replacement allocation schema; service registers mutation guards."""
from datetime import datetime
from infrastructure.extensions import db

class ReplacementSettlement(db.Model):
    __tablename__ = 'replacement_settlement'
    id = db.Column(db.Integer, primary_key=True)
    revision_id = db.Column(db.Integer, db.ForeignKey('report_revision.id'), nullable=False, unique=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False, index=True)
    revision_no = db.Column(db.Integer, nullable=False)
    previous_id = db.Column(db.Integer, db.ForeignKey('replacement_settlement.id'))
    old_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    new_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    old_amount = db.Column(db.Numeric(14, 2), nullable=False)
    new_amount = db.Column(db.Numeric(14, 2), nullable=False)
    linked_paid_amount = db.Column(db.Numeric(14, 2), nullable=False)
    verified_paid_amount = db.Column(db.Numeric(14, 2), nullable=False)
    preview_sha256 = db.Column(db.String(64), nullable=False)
    snapshot_json = db.Column(db.Text, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('order_id', 'revision_no', name='uq_settlement_order_revision'),
        db.CheckConstraint('old_amount >= 0 AND new_amount >= 0 AND linked_paid_amount >= 0 AND verified_paid_amount >= linked_paid_amount', name='ck_settlement_nonnegative'),
        db.CheckConstraint('old_doctor_id <> new_doctor_id', name='ck_settlement_distinct_physicians'),
    )

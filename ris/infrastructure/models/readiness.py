"""Persisted schema definitions; no web/application initialization."""
from datetime import datetime, date
import json
from infrastructure.extensions import db

class JourneyEvent(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    stage=db.Column(db.String(50),nullable=False,index=True)
    entered_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    completed_at=db.Column(db.DateTime,index=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'))
    notes=db.Column(db.String(500),default='')
    order=db.relationship('Order',foreign_keys=[order_id])
    user=db.relationship('User',foreign_keys=[user_id])

class ProcedureQualityRule(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    modality=db.Column(db.String(30),nullable=False,index=True)
    procedure_pattern=db.Column(db.String(180),nullable=False,index=True)
    min_images=db.Column(db.Integer,default=0)
    warning_images=db.Column(db.Integer,default=0)
    required_series=db.Column(db.Text,default='')
    require_history=db.Column(db.Boolean,default=True)
    require_attachments=db.Column(db.Boolean,default=False)
    require_pacs_study=db.Column(db.Boolean,default=True)
    block_auto_assign=db.Column(db.Boolean,default=True)
    tolerance_percent=db.Column(db.Integer,default=15)
    active=db.Column(db.Boolean,default=True,index=True)

class CaseReadiness(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),unique=True,nullable=False,index=True)
    status=db.Column(db.String(40),default='NOT_CHECKED',index=True)
    score=db.Column(db.Integer,default=0)
    image_count=db.Column(db.Integer,default=0)
    expected_min_images=db.Column(db.Integer,default=0)
    missing_history=db.Column(db.Boolean,default=False)
    missing_attachments=db.Column(db.Boolean,default=False)

    # v5.33 workflow readiness
    missing_documents=db.Column(db.Boolean,default=False)
    missing_notes=db.Column(db.Boolean,default=False)

    missing_pacs=db.Column(db.Boolean,default=False)
    incomplete_images=db.Column(db.Boolean,default=False)
    missing_series=db.Column(db.Boolean,default=False)
    series_evidence_json=db.Column(db.Text,default='[]')
    facts_sha256=db.Column(db.String(64),default='')
    series_checked_at=db.Column(db.DateTime)
    details_json=db.Column(db.Text,default='{}')
    checked_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    override_reason=db.Column(db.Text,default='')
    override_by=db.Column(db.Integer,db.ForeignKey('user.id'))

class ReadinessSeriesAlias(db.Model):
    __tablename__='readiness_series_alias'
    id=db.Column(db.Integer,primary_key=True)
    rule_id=db.Column(db.Integer,db.ForeignKey('procedure_quality_rule.id'),nullable=False,index=True)
    source_alias=db.Column(db.String(255),nullable=False)
    alias_normalized=db.Column(db.String(255),nullable=False)
    canonical_series=db.Column(db.String(120),nullable=False)
    match_field=db.Column(db.String(20),nullable=False,default='EITHER')
    active=db.Column(db.Boolean,nullable=False,default=True,index=True)
    created_by=db.Column(db.Integer)
    reason=db.Column(db.String(500),nullable=False,default='')
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    rule=db.relationship('ProcedureQualityRule',foreign_keys=[rule_id])
    __table_args__=(db.UniqueConstraint('rule_id','alias_normalized','match_field',name='uq_readiness_series_alias_rule_value_field'),)

class CaseReadinessOverride(db.Model):
    __tablename__='case_readiness_override'
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    blocker=db.Column(db.String(80),nullable=False)
    override_value=db.Column(db.String(255),nullable=False)
    active=db.Column(db.Boolean,nullable=False,default=True,index=True)
    reason=db.Column(db.String(500),nullable=False)
    actor_user_id=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    deactivated_at=db.Column(db.DateTime)

class CaseExceptionResolutionEvent(db.Model):
    __tablename__='case_exception_resolution_event'
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    action=db.Column(db.String(60),nullable=False,index=True)
    blocker=db.Column(db.String(80),nullable=False,default='')
    old_value=db.Column(db.String(500),nullable=False,default='')
    new_value=db.Column(db.String(500),nullable=False,default='')
    reason=db.Column(db.String(500),nullable=False)
    actor_user_id=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow,index=True)
    order=db.relationship('Order',foreign_keys=[order_id])

class CaseWorkflowEvent(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    event_type=db.Column(db.String(60),nullable=False,index=True)
    owner_role=db.Column(db.String(60),default='')
    reason_code=db.Column(db.String(100),default='')
    note=db.Column(db.Text,default='')
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)

class CaseReturnReason(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(100),unique=True,nullable=False)
    label=db.Column(db.String(180),nullable=False)
    route_to=db.Column(db.String(60),default='TECHNICIAN')
    active=db.Column(db.Boolean,default=True,index=True)

class TATPolicy(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    priority=db.Column(db.String(30),default='ROUTINE',index=True)
    modality=db.Column(db.String(30),default='*',index=True)
    ready_to_assign_min=db.Column(db.Integer,default=10)
    assign_to_accept_min=db.Column(db.Integer,default=5)
    accept_to_final_min=db.Column(db.Integer,default=60)
    total_tat_min=db.Column(db.Integer,default=120)
    active=db.Column(db.Boolean,default=True)

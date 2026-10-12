"""Persisted schema definitions; no web/application initialization."""
from datetime import datetime, date
import json
from infrastructure.extensions import db

class DoctorAvailabilityState(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),unique=True,nullable=False,index=True)
    state=db.Column(db.String(30),default='AVAILABLE',index=True) # AVAILABLE/BUSY/AWAY/OFFLINE
    busy_until=db.Column(db.DateTime)
    last_seen_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    user=db.relationship('User',foreign_keys=[user_id])

class AssignmentOfferPolicy(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(120),default='Default')
    enabled=db.Column(db.Boolean,default=True,index=True)
    mode=db.Column(db.String(30),default='ONLINE_PREFERRED') # ONLINE_ONLY/ONLINE_PREFERRED/ALL
    routine_timeout_seconds=db.Column(db.Integer,default=300)
    urgent_timeout_seconds=db.Column(db.Integer,default=120)
    stat_timeout_seconds=db.Column(db.Integer,default=60)
    busy_snooze_minutes=db.Column(db.Integer,default=30)
    max_offer_attempts=db.Column(db.Integer,default=5)
    notification_channels=db.Column(db.String(120),default='INAPP,WHATSAPP,TELEGRAM,EMAIL')
    updated_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class AssignmentStrategy(db.Model):
    """
    Admin-configurable smart assignment strategy.

    Priority:
    Lower number = higher priority.

    Matching hierarchy can be:
    procedure -> modality/branch -> modality -> branch -> global.
    """
    __tablename__ = 'assignment_strategy'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(160), nullable=False, unique=True)
    enabled = db.Column(db.Boolean, default=True, index=True)
    priority = db.Column(db.Integer, default=100, index=True)

    # Scope
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'))
    modality = db.Column(db.String(30), default='', index=True)
    procedure_pattern = db.Column(db.String(180), default='')

    # Assignment behavior
    assignment_mode = db.Column(
        db.String(30),
        default='OFFER_ACCEPT'
    )
    # OFFER_ACCEPT / DIRECT_ASSIGN / OPEN_POOL / HYBRID / MANUAL_ONLY

    fallback_mode = db.Column(
        db.String(30),
        default='OPEN_POOL'
    )
    # OPEN_POOL / COORDINATOR / MANUAL_ONLY

    # Readiness actions
    pacs_missing_action = db.Column(db.String(20), default='BLOCK')
    images_incomplete_action = db.Column(db.String(20), default='BLOCK')
    documents_missing_action = db.Column(db.String(20), default='WARN')
    notes_missing_action = db.Column(db.String(20), default='WARN')
    attachments_missing_action = db.Column(db.String(20), default='WARN')
    history_missing_action = db.Column(db.String(20), default='IGNORE')

    # Doctor matching
    require_modality_match = db.Column(db.Boolean, default=True)
    require_branch_match = db.Column(db.Boolean, default=False)
    require_online = db.Column(db.Boolean, default=False)
    prefer_online = db.Column(db.Boolean, default=True)

    # Imaging rules
    min_images = db.Column(db.Integer, default=0)
    min_completion_percent = db.Column(db.Integer, default=0)
    stable_seconds = db.Column(db.Integer, default=120)

    # Offer timing
    routine_timeout_seconds = db.Column(db.Integer, default=300)
    urgent_timeout_seconds = db.Column(db.Integer, default=120)
    stat_timeout_seconds = db.Column(db.Integer, default=60)

    busy_snooze_minutes = db.Column(db.Integer, default=30)
    max_offer_attempts = db.Column(db.Integer, default=5)

    # Optional schedule window
    active_from = db.Column(db.String(5), default='')
    active_to = db.Column(db.String(5), default='')

    version_no = db.Column(db.Integer, default=1)

    updated_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

class AssignmentStrategyVersion(db.Model):
    """
    Immutable history of every admin strategy change.
    """
    __tablename__ = 'assignment_strategy_version'

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey('assignment_strategy.id'),
        nullable=False,
        index=True
    )

    version_no = db.Column(db.Integer, nullable=False)

    snapshot_json = db.Column(
        db.Text,
        nullable=False
    )

    changed_by = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    change_note = db.Column(
        db.String(500),
        default=''
    )

    changed_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        index=True
    )

class AssignmentVisit(db.Model):
    assignment_mode = db.Column(db.String(20), default='AUTO')
    registration_open = db.Column(db.Boolean, default=False)
    __tablename__ = 'assignment_visit'
    sequence_id = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.String(36), nullable=False, unique=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'))
    visit_date = db.Column(db.Date, nullable=False)
    preferred_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class AssignmentDistributionPolicy(db.Model):
    __tablename__ = 'assignment_distribution_policy'
    id = db.Column(db.Integer, primary_key=True)
    selection_mode = db.Column(db.String(30), nullable=False, default='LEAST_ACTIVE')
    max_active_cases = db.Column(db.Integer, nullable=False, default=20)
    reclaim_enabled = db.Column(db.Boolean, nullable=False, default=True)
    urgent_percent = db.Column(db.Integer, nullable=False, default=50)
    stat_percent = db.Column(db.Integer, nullable=False, default=25)
    rules_json = db.Column(db.Text, nullable=False)
    special_rules_json = db.Column(db.Text, nullable=False, default='[]')
    version_no = db.Column(db.Integer, nullable=False, default=1)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AssignmentOffer(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    doctor_user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    attempt_no=db.Column(db.Integer,default=1)
    status=db.Column(db.String(30),default='PENDING',index=True) # PENDING/ACCEPTED/BUSY/REJECTED/TIMEOUT/CANCELLED
    offered_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    expires_at=db.Column(db.DateTime,nullable=False,index=True)
    responded_at=db.Column(db.DateTime)
    response_note=db.Column(db.String(500),default='')
    channel_summary=db.Column(db.String(300),default='')
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    order=db.relationship('Order',foreign_keys=[order_id])
    doctor=db.relationship('User',foreign_keys=[doctor_user_id])

class AssignmentEscalationEvent(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    offer_id=db.Column(db.Integer,db.ForeignKey('assignment_offer.id'),index=True)
    event_type=db.Column(db.String(50),nullable=False,index=True)
    details=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'))

class DoctorAssignmentProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    modalities = db.Column(db.String(200), default='')
    specialties = db.Column(db.String(300), default='')
    branches = db.Column(db.String(200), default='')
    max_active_cases = db.Column(db.Integer, default=20)
    auto_assign = db.Column(db.Boolean, default=True)
    available = db.Column(db.Boolean, default=True)
    priority_weight = db.Column(db.Integer, default=100)
    user = db.relationship('User', foreign_keys=[user_id])

class CaseAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False, index=True)
    doctor_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    assigned_by = db.Column(db.Integer)
    assignment_type = db.Column(db.String(20), default='MANUAL')
    active = db.Column(db.Boolean, default=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    unassigned_at = db.Column(db.DateTime)
    notes = db.Column(db.String(500), default='')
    start_deadline_at = db.Column(db.DateTime, index=True)
    start_timeout_seconds = db.Column(db.Integer)
    reading_started_at = db.Column(db.DateTime)
    distribution_snapshot_json = db.Column(db.Text)
    order = db.relationship('Order', foreign_keys=[order_id])
    doctor = db.relationship('User', foreign_keys=[doctor_user_id])
    __table_args__ = (
        db.Index(
            'uq_case_assignment_one_active_per_order',
            'order_id',
            unique=True,
            postgresql_where=db.text('active IS TRUE'),
            sqlite_where=db.text('active = 1'),
        ),
    )

class CoordinatorTask(db.Model):
    __tablename__='coordinator_task'
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    report_id=db.Column(db.Integer,db.ForeignKey('report.id'),nullable=False,index=True)
    assigned_to=db.Column(db.Integer,db.ForeignKey('user.id'))
    status=db.Column(db.String(40),default='PENDING_FORMATTING',index=True)
    doctor_note=db.Column(db.Text,default='')
    coordinator_note=db.Column(db.Text,default='')
    created_by=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    started_at=db.Column(db.DateTime)
    completed_at=db.Column(db.DateTime)
    returned_at=db.Column(db.DateTime)
    order=db.relationship('Order',foreign_keys=[order_id])
    report=db.relationship('Report',foreign_keys=[report_id])
    assignee=db.relationship('User',foreign_keys=[assigned_to])

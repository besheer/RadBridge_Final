"""Persisted schema definitions; no web/application initialization."""
from datetime import datetime, date
import json
from infrastructure.extensions import db

class DicomEndpoint(db.Model):
    __tablename__='dicom_endpoint'
    id=db.Column(db.Integer,primary_key=True)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),nullable=False,index=True)
    kind=db.Column(db.String(20),nullable=False)
    ae_title=db.Column(db.String(16),nullable=False)
    calling_ae=db.Column(db.String(16),nullable=False,default='RADBRIDGERIS')
    host=db.Column(db.String(253),nullable=False,default='')
    port=db.Column(db.Integer,nullable=False,default=104)
    active=db.Column(db.Boolean,nullable=False,default=False)
    echo_result=db.Column(db.String(20),nullable=False,default='NOT_TESTED')
    echo_message=db.Column(db.String(240),nullable=False,default='')
    echo_checked_at=db.Column(db.DateTime)
    echo_elapsed_ms=db.Column(db.Integer)
    branch=db.relationship('Branch')
    __table_args__=(db.UniqueConstraint('branch_id','kind',name='uq_dicom_endpoint_branch_kind'),)

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    modality = db.Column(db.String(10), nullable=False)
    ae_title = db.Column(db.String(40), nullable=False)
    ip = db.Column(db.String(80), default='')
    port = db.Column(db.Integer, default=104)
    room = db.Column(db.String(80), default='')
    priority = db.Column(db.Integer, default=100)
    active = db.Column(db.Boolean, default=True)
    operational_status = db.Column(db.String(30), default='ACTIVE')
    booking_enabled = db.Column(db.Boolean, default=True)
    workday_start = db.Column(db.String(5), default='08:00')
    workday_end = db.Column(db.String(5), default='22:00')
    branch = db.relationship('Branch')

class ExternalPriorStudy(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),nullable=False,index=True)
    linked_order_id=db.Column(db.Integer,db.ForeignKey('order.id'),index=True)
    source_type=db.Column(db.String(30),default='UPLOAD',index=True)
    study_date=db.Column(db.Date)
    modality=db.Column(db.String(30),default='',index=True)
    study_description=db.Column(db.String(300),default='')
    external_patient_name=db.Column(db.String(200),default='')
    external_patient_id=db.Column(db.String(120),default='')
    external_dob=db.Column(db.String(40),default='')
    file_path=db.Column(db.String(700),nullable=False)
    original_name=db.Column(db.String(300),default='')
    dicom_metadata_json=db.Column(db.Text,default='{}')
    match_status=db.Column(db.String(30),default='REVIEW',index=True)
    match_score=db.Column(db.Float,default=0)
    imported_to_pacs=db.Column(db.Boolean,default=False)
    uploaded_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)

class PriorStudySelection(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    prior_order_id=db.Column(db.Integer,db.ForeignKey('order.id'),index=True)
    external_prior_id=db.Column(db.Integer,db.ForeignKey('external_prior_study.id'),index=True)
    selected_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    selected_at=db.Column(db.DateTime,default=datetime.utcnow)
    include_in_ai=db.Column(db.Boolean,default=True)

class ImagingAIProvider(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    provider_key=db.Column(db.String(60),unique=True,nullable=False,index=True)
    enabled=db.Column(db.Boolean,default=False,index=True)
    base_url=db.Column(db.String(500),default='')
    model_name=db.Column(db.String(180),default='')
    modalities=db.Column(db.String(120),default='XR,CT,MR')
    timeout_seconds=db.Column(db.Integer,default=180)
    secret_env_name=db.Column(db.String(120),default='RIS_IMAGING_AI_TOKEN')
    updated_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class ImagingAIAnalysis(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    provider_key=db.Column(db.String(60),default='')
    model_name=db.Column(db.String(180),default='')
    study_instance_uid=db.Column(db.String(180),default='',index=True)
    accession=db.Column(db.String(120),default='',index=True)
    status=db.Column(db.String(40),default='NOT_ANALYZED',index=True)
    demographic_status=db.Column(db.String(40),default='NOT_CHECKED',index=True)
    demographic_score=db.Column(db.Float,default=0)
    demographic_details_json=db.Column(db.Text,default='{}')
    structured_findings_json=db.Column(db.Text,default='{}')
    summary_text=db.Column(db.Text,default='')
    uncertainty_text=db.Column(db.Text,default='')
    raw_response_json=db.Column(db.Text,default='{}')
    requested_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    requested_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    completed_at=db.Column(db.DateTime)
    reviewed_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    reviewed_at=db.Column(db.DateTime)
    error_text=db.Column(db.Text,default='')
    order=db.relationship('Order',foreign_keys=[order_id])

class DemographicOverrideAudit(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    analysis_id=db.Column(db.Integer,db.ForeignKey('imaging_ai_analysis.id'),nullable=False,index=True)
    original_status=db.Column(db.String(40),default='')
    override_reason=db.Column(db.Text,nullable=False)
    overridden_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    overridden_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)

class DeviceSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(5), default='09:00')
    end_time = db.Column(db.String(5), default='21:00')
    break_start = db.Column(db.String(5), default='')
    break_end = db.Column(db.String(5), default='')
    active = db.Column(db.Boolean, default=True)
    device = db.relationship('Device', foreign_keys=[device_id])

class DeviceBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(160), default='Maintenance')
    device = db.relationship('Device', foreign_keys=[device_id])

class PacsStudyMatch(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    orthanc_study_id=db.Column(db.String(120),unique=True,nullable=False,index=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    match_method=db.Column(db.String(40),default='MANUAL')
    confidence=db.Column(db.String(20),default='CONFIRMED')
    pacs_patient_id=db.Column(db.String(80),default='')
    pacs_patient_name=db.Column(db.String(180),default='')
    pacs_accession=db.Column(db.String(120),default='')
    confirmed_by=db.Column(db.Integer)
    confirmed_at=db.Column(db.DateTime,default=datetime.utcnow)
    notes=db.Column(db.String(500),default='')
    is_current=db.Column(db.Boolean,nullable=False,default=False,index=True)
    superseded_at=db.Column(db.DateTime)
    superseded_by=db.Column(db.Integer)
    superseded_reason=db.Column(db.String(500),nullable=False,default='')
    order=db.relationship('Order',foreign_keys=[order_id])

class PacsExamLink(db.Model):
    __tablename__='pacs_exam_link'
    id=db.Column(db.Integer,primary_key=True)
    orthanc_study_id=db.Column(db.String(120),nullable=False,index=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    link_role=db.Column(db.String(20),nullable=False,default='SECONDARY')
    active=db.Column(db.Boolean,nullable=False,default=True)
    reason=db.Column(db.String(500),nullable=False)
    created_by=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    removed_by=db.Column(db.Integer)
    removed_at=db.Column(db.DateTime)

class PacsResolutionEvent(db.Model):
    __tablename__='pacs_resolution_event'
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    event_type=db.Column(db.String(50),nullable=False)
    old_orthanc_study_id=db.Column(db.String(120),nullable=False,default='')
    new_orthanc_study_id=db.Column(db.String(120),nullable=False,default='')
    old_study_instance_uid=db.Column(db.String(180),nullable=False,default='')
    new_study_instance_uid=db.Column(db.String(180),nullable=False,default='')
    reason=db.Column(db.String(500),nullable=False)
    actor_user_id=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)

class DicomCorrection(db.Model):
    __tablename__='dicom_correction'
    id=db.Column(db.Integer,primary_key=True)
    source_study_id=db.Column(db.String(120),nullable=False,unique=True)
    new_study_id=db.Column(db.String(120),default='',index=True)
    new_uid=db.Column(db.String(180),default='')
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    actor_user_id=db.Column(db.Integer,nullable=False)
    status=db.Column(db.String(30),nullable=False,index=True)
    reason=db.Column(db.String(500),nullable=False)
    before_json=db.Column(db.Text,nullable=False)
    after_json=db.Column(db.Text,nullable=False)
    error_code=db.Column(db.String(80),default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
    finished_at=db.Column(db.DateTime)

class PacsStudyInbox(db.Model):
    __tablename__='pacs_study_inbox'
    id=db.Column(db.Integer,primary_key=True)
    orthanc_study_id=db.Column(db.String(120),unique=True,nullable=False,index=True)
    study_instance_uid=db.Column(db.String(180),unique=True,index=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),index=True)
    pacs_patient_id=db.Column(db.String(80),default='')
    pacs_patient_name=db.Column(db.String(180),default='')
    accession=db.Column(db.String(120),default='',index=True)
    modality=db.Column(db.String(30),default='')
    study_description=db.Column(db.String(255),default='')
    source_ae=db.Column(db.String(80),default='')
    image_count=db.Column(db.Integer,default=0)
    state=db.Column(db.String(40),default='NEW',index=True) # NEW/LINKED/AUTO_CREATED/REVIEW/ERROR
    match_method=db.Column(db.String(60),default='')
    error_text=db.Column(db.Text,default='')
    first_seen_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    last_seen_at=db.Column(db.DateTime,default=datetime.utcnow)
    order=db.relationship('Order',foreign_keys=[order_id])

class DiscoveredDicomNode(db.Model):
    __tablename__='discovered_dicom_node'
    id=db.Column(db.Integer,primary_key=True)
    ae_title=db.Column(db.String(80),nullable=False,index=True)
    host=db.Column(db.String(120),default='',index=True)
    port=db.Column(db.Integer,default=0)
    node_type=db.Column(db.String(30),default='UNKNOWN')  # MODALITY/VIEWER/UNKNOWN
    modality=db.Column(db.String(30),default='')
    source_description=db.Column(db.String(255),default='')
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'))
    status=db.Column(db.String(30),default='PENDING',index=True) # PENDING/APPROVED/BLOCKED
    studies_seen=db.Column(db.Integer,default=0)
    first_seen_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    last_seen_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    approved_at=db.Column(db.DateTime)
    approved_by=db.Column(db.Integer)
    notes=db.Column(db.Text,default='')
    branch=db.relationship('Branch',foreign_keys=[branch_id])
    __table_args__=(db.UniqueConstraint('ae_title','host',name='uq_discovered_dicom_ae_host'),)

class DicomDestination(db.Model):
    __tablename__='dicom_destination'
    id=db.Column(db.Integer,primary_key=True)
    key=db.Column(db.String(60),unique=True,nullable=False,index=True)
    name=db.Column(db.String(160),nullable=False)
    ae_title=db.Column(db.String(40),nullable=False)
    host=db.Column(db.String(120),nullable=False)
    port=db.Column(db.Integer,nullable=False,default=104)
    destination_type=db.Column(db.String(30),default='PACS') # MODALITY/PACS/BACKUP/ARCHIVE/WORKSTATION
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'))
    active=db.Column(db.Boolean,default=True)
    allow_manual_send=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    branch=db.relationship('Branch',foreign_keys=[branch_id])

class PacsRoutingRule(db.Model):
    __tablename__='pacs_routing_rule'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),nullable=False)
    destination_id=db.Column(db.Integer,db.ForeignKey('dicom_destination.id'),nullable=False)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'))
    modality=db.Column(db.String(30),default='')
    source_ae=db.Column(db.String(80),default='')
    min_priority=db.Column(db.String(20),default='')
    active=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    destination=db.relationship('DicomDestination',foreign_keys=[destination_id])
    branch=db.relationship('Branch',foreign_keys=[branch_id])

class PacsTransferJob(db.Model):
    __tablename__='pacs_transfer_job'
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),index=True)
    orthanc_study_id=db.Column(db.String(120),nullable=False,index=True)
    destination_id=db.Column(db.Integer,db.ForeignKey('dicom_destination.id'),nullable=False,index=True)
    reason=db.Column(db.String(40),default='MANUAL')
    status=db.Column(db.String(30),default='PENDING',index=True)
    attempts=db.Column(db.Integer,default=0)
    last_error=db.Column(db.Text,default='')
    created_by=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    started_at=db.Column(db.DateTime)
    completed_at=db.Column(db.DateTime)
    verified_at=db.Column(db.DateTime)
    cancelled_at=db.Column(db.DateTime)
    progress_total=db.Column(db.Integer,default=0)
    progress_sent=db.Column(db.Integer,default=0)
    destination=db.relationship('DicomDestination',foreign_keys=[destination_id])
    order=db.relationship('Order',foreign_keys=[order_id])

class CorrectionRequest(db.Model):
    __tablename__='correction_request'
    __table_args__=(
        db.CheckConstraint(
            "request_type IN ('WRONG_IMAGES','WRONG_DEMOGRAPHICS','WRONG_ORDER','WRONG_ACCESSION','DUPLICATE_CASE','CANCEL_ORDER','WRONG_REPORT','OTHER')",
            name='ck_correction_request_type',
        ),
        db.CheckConstraint(
            "status IN ('NEW','UNDER_REVIEW','NEED_INFO','APPROVED','REJECTED','COMPLETED')",
            name='ck_correction_request_status',
        ),
        db.Index(
            'uq_correction_request_open_order_type',
            'order_id',
            'request_type',
            unique=True,
            postgresql_where=db.text("status IN ('NEW','UNDER_REVIEW','NEED_INFO','APPROVED')"),
            sqlite_where=db.text("status IN ('NEW','UNDER_REVIEW','NEED_INFO','APPROVED')"),
        ),
    )
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    request_type=db.Column(db.String(40),nullable=False,index=True)
    status=db.Column(db.String(30),nullable=False,default='NEW',index=True)
    reason=db.Column(db.Text,nullable=False)
    requested_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    assigned_to=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    review_note=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False,index=True)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
    reviewed_at=db.Column(db.DateTime)
    closed_at=db.Column(db.DateTime)
    order=db.relationship('Order',foreign_keys=[order_id])
    branch=db.relationship('Branch',foreign_keys=[branch_id])
    requester=db.relationship('User',foreign_keys=[requested_by])
    assignee=db.relationship('User',foreign_keys=[assigned_to])

class PatientDemographicsCorrection(db.Model):
    __tablename__='patient_demographics_correction'
    id=db.Column(db.Integer,primary_key=True)
    correction_request_id=db.Column(db.Integer,db.ForeignKey('correction_request.id'),nullable=False,unique=True)
    patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),nullable=False,index=True)
    field_name=db.Column(db.String(40),nullable=False)
    old_value=db.Column(db.Text,nullable=False)
    proposed_value=db.Column(db.Text,nullable=False)
    snapshot_hash=db.Column(db.String(64),nullable=False)
    impact_json=db.Column(db.Text,nullable=False)
    request=db.relationship('CorrectionRequest',backref=db.backref('demographic_detail',uselist=False))

class CorrectionExecution(db.Model):
    __tablename__='correction_execution'

    id=db.Column(
        db.Integer,
        primary_key=True
    )

    correction_request_id=db.Column(
        db.Integer,
        db.ForeignKey('correction_request.id'),
        nullable=False,
        unique=True,
        index=True
    )

    order_id=db.Column(
        db.Integer,
        db.ForeignKey('order.id'),
        nullable=False,
        index=True
    )

    branch_id=db.Column(
        db.Integer,
        db.ForeignKey('branch.id'),
        nullable=True,
        index=True
    )

    execution_type=db.Column(
        db.String(40),
        nullable=False,
        index=True
    )

    status=db.Column(
        db.String(40),
        nullable=False,
        default='READY_FOR_EXECUTION',
        index=True
    )

    state_version=db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    claimed_by=db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True,
        index=True
    )

    executed_by=db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True
    )

    request_snapshot_json=db.Column(
        db.Text,
        nullable=False,
        default='{}'
    )

    preflight_snapshot_json=db.Column(
        db.Text,
        nullable=False,
        default='{}'
    )

    result_snapshot_json=db.Column(
        db.Text,
        nullable=False,
        default='{}'
    )

    confirmation_token_hash=db.Column(
        db.String(128),
        nullable=True
    )

    confirmation_expires_at=db.Column(
        db.DateTime,
        nullable=True
    )

    failure_code=db.Column(
        db.String(80),
        nullable=True
    )

    failure_message=db.Column(
        db.Text,
        nullable=True
    )

    created_at=db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at=db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    claimed_at=db.Column(
        db.DateTime,
        nullable=True
    )

    started_at=db.Column(
        db.DateTime,
        nullable=True
    )

    executed_at=db.Column(
        db.DateTime,
        nullable=True
    )

    verified_at=db.Column(
        db.DateTime,
        nullable=True
    )

    failed_at=db.Column(
        db.DateTime,
        nullable=True
    )

"""Persisted schema definitions; no web/application initialization."""
from datetime import datetime, date
import json
from infrastructure.extensions import db

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    dob = db.Column(db.String(8))
    dob_estimated = db.Column(db.Boolean, default=False, nullable=False)
    sex = db.Column(db.String(1))
    phone = db.Column(db.String(30))
    national_id = db.Column(db.String(30))
    address = db.Column(db.String(255))
    email = db.Column(db.String(180), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    worklist_name = db.Column(db.String(180), default='')

class Procedure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(180), nullable=False)
    name_ar = db.Column(db.String(180), default='')
    category = db.Column(db.String(80), default='')
    modality = db.Column(db.String(10), nullable=False)
    body_part = db.Column(db.String(80), default='')
    base_price = db.Column(db.Float, default=0)
    duration_min = db.Column(db.Integer, default=20)
    contrast = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)

class ProcedureBranch(db.Model):
    __tablename__='procedure_branch'
    id=db.Column(db.Integer,primary_key=True)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),nullable=False,index=True)
    procedure_id=db.Column(db.Integer,db.ForeignKey('procedure.id'),nullable=False,index=True)
    active=db.Column(db.Boolean,default=True,nullable=False)
    branch=db.relationship('Branch')
    procedure=db.relationship('Procedure')
    __table_args__=(db.UniqueConstraint('branch_id','procedure_id',name='uq_procedure_branch'),)

class BookingBlock(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    block_type=db.Column(db.String(40),nullable=False,index=True)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    device_id=db.Column(db.Integer,db.ForeignKey('device.id'),index=True)
    procedure_id=db.Column(db.Integer,db.ForeignKey('procedure.id'),index=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    start_at=db.Column(db.DateTime,nullable=False,index=True)
    end_at=db.Column(db.DateTime,nullable=False,index=True)
    reason_code=db.Column(db.String(60),default='OTHER')
    reason_text=db.Column(db.String(500),default='')
    active=db.Column(db.Boolean,default=True,index=True)
    created_by=db.Column(db.Integer)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    branch=db.relationship('Branch',foreign_keys=[branch_id])
    device=db.relationship('Device',foreign_keys=[device_id])
    procedure=db.relationship('Procedure',foreign_keys=[procedure_id])

class FieldRule(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    field_key=db.Column(db.String(100),unique=True,nullable=False,index=True)
    label_en=db.Column(db.String(160),default='')
    label_ar=db.Column(db.String(160),default='')
    data_type=db.Column(db.String(30),default='ANY')
    min_length=db.Column(db.Integer); max_length=db.Column(db.Integer); exact_length=db.Column(db.Integer)
    required=db.Column(db.Boolean,default=False); visible=db.Column(db.Boolean,default=True)
    read_only=db.Column(db.Boolean,default=False); allow_spaces=db.Column(db.Boolean,default=True)
    regex_pattern=db.Column(db.String(500),default='')
    updated_by=db.Column(db.Integer,db.ForeignKey('user.id')); updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class UserRegistrationPreference(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),unique=True,nullable=False,index=True)
    style_key=db.Column(db.String(30),default='MODERN')

class RegistrationDefault(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    is_global=db.Column(db.Boolean,default=False,index=True)
    default_branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    default_department=db.Column(db.String(100),default='')
    default_procedure_id=db.Column(db.Integer,db.ForeignKey('procedure.id'),index=True)
    default_contract_id=db.Column(db.Integer,db.ForeignKey('contract.id'),index=True)
    default_referrer_id=db.Column(db.Integer,db.ForeignKey('referring_doctor.id'),index=True)
    default_priority=db.Column(db.String(30),default='ROUTINE')
    default_payment_method=db.Column(db.String(40),default='')
    default_patient_mode=db.Column(db.String(20),default='new')
    active=db.Column(db.Boolean,default=True,index=True)
    updated_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    user=db.relationship('User',foreign_keys=[user_id])
    branch=db.relationship('Branch')
    procedure=db.relationship('Procedure')
    contract=db.relationship('Contract')
    referrer=db.relationship('ReferringDoctor')

class PatientAlert(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),nullable=False,index=True)
    alert_type=db.Column(db.String(50),nullable=False,index=True)
    title=db.Column(db.String(180),default=''); notes=db.Column(db.Text,default='')
    amount=db.Column(db.Float); branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'))
    status=db.Column(db.String(20),default='OPEN',index=True)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id')); resolved_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at=db.Column(db.DateTime,default=datetime.utcnow); resolved_at=db.Column(db.DateTime)

class PatientDemographicsExtra(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),unique=True,nullable=False,index=True)
    nationality=db.Column(db.String(100),default='')
    id_type=db.Column(db.String(30),default='NATIONAL_ID')
    other_id=db.Column(db.String(80),default='')
    patient=db.relationship('Patient',foreign_keys=[patient_id])

class SmartIntakeSession(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    session_key=db.Column(db.String(80),unique=True,nullable=False,index=True)
    patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),index=True)
    status=db.Column(db.String(40),default='UPLOADING',index=True) # UPLOADING/EXTRACTED/REVIEW/READY/COMPLETED
    extracted_json=db.Column(db.Text,default='{}')
    matched_patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),index=True)
    suggested_procedure_id=db.Column(db.Integer,db.ForeignKey('procedure.id'),index=True)
    suggested_contract_id=db.Column(db.Integer,db.ForeignKey('contract.id'),index=True)
    matched_patient_score=db.Column(db.Float,default=0)
    match_resolution=db.Column(db.String(40),default='NOT_CHECKED',index=True)
    review_notes=db.Column(db.Text,default='')
    reviewed_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    reviewed_at=db.Column(db.DateTime)
    commit_key=db.Column(db.String(64),unique=True,index=True)
    commit_action=db.Column(db.String(30),default='')
    committed_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    committed_at=db.Column(db.DateTime)
    completed_at=db.Column(db.DateTime)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class SmartIntakeDocument(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    intake_id=db.Column(db.Integer,db.ForeignKey('smart_intake_session.id'),nullable=False,index=True)
    document_type=db.Column(db.String(50),nullable=False,index=True)
    original_name=db.Column(db.String(300),default='')
    file_path=db.Column(db.String(700),nullable=False)
    mime_type=db.Column(db.String(120),default='')
    status=db.Column(db.String(40),default='UPLOADED',index=True) # UPLOADED/OCR_DONE/REVIEW_REQUIRED/APPROVED/REJECTED
    ocr_text=db.Column(db.Text,default='')
    extracted_json=db.Column(db.Text,default='{}')
    confidence=db.Column(db.Float,default=0)
    content_sha256=db.Column(db.String(64),default='',index=True)
    ocr_provider_key=db.Column(db.String(60),default='')
    ocr_config_hash=db.Column(db.String(64),default='')
    ocr_error=db.Column(db.String(500),default='')
    review_notes=db.Column(db.Text,default='')
    patient_document_id=db.Column(db.Integer,db.ForeignKey('patient_document.id'),index=True)
    reviewed_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    reviewed_at=db.Column(db.DateTime)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)

class SmartIntakeFieldReview(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    intake_id=db.Column(db.Integer,db.ForeignKey('smart_intake_session.id'),nullable=False,index=True)
    source_document_id=db.Column(db.Integer,db.ForeignKey('smart_intake_document.id'),index=True)
    field_key=db.Column(db.String(80),nullable=False,index=True)
    source_type=db.Column(db.String(50),default='')
    extracted_value=db.Column(db.Text,default='')
    normalized_value=db.Column(db.Text,default='')
    final_value=db.Column(db.Text,default='')
    confidence=db.Column(db.Float,default=0)
    validation_status=db.Column(db.String(30),default='REVIEW',index=True)
    validation_message=db.Column(db.String(500),default='')
    review_status=db.Column(db.String(30),default='PENDING',index=True)
    reviewed_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    reviewed_at=db.Column(db.DateTime)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    __table_args__=(db.UniqueConstraint('intake_id','field_key',name='uq_smart_intake_field_review'),)

class OCRProviderSetting(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    provider_key=db.Column(db.String(60),unique=True,nullable=False,index=True)
    enabled=db.Column(db.Boolean,default=False,index=True)
    base_url=db.Column(db.String(500),default='')
    model_name=db.Column(db.String(180),default='')
    timeout_seconds=db.Column(db.Integer,default=60)
    secret_env_name=db.Column(db.String(120),default='RIS_OCR_API_KEY')
    validation_status=db.Column(db.String(40),default='NOT_CHECKED',index=True)
    validation_details=db.Column(db.Text,default='{}')
    validation_config_hash=db.Column(db.String(64),default='',index=True)
    validation_latency_ms=db.Column(db.Integer)
    validated_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    validated_at=db.Column(db.DateTime)
    updated_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    patient_share_percent = db.Column(db.Float, default=0)
    discount_percent = db.Column(db.Float, default=0)
    approval_required = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)

class ContractPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'), nullable=False)
    procedure_id = db.Column(db.Integer, db.ForeignKey('procedure.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    patient_share_percent = db.Column(db.Float)
    contract = db.relationship('Contract')
    procedure = db.relationship('Procedure')
    __table_args__ = (db.UniqueConstraint('contract_id','procedure_id', name='uq_contract_proc'),)

class ReferringDoctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    specialty = db.Column(db.String(120), default='')
    phone = db.Column(db.String(40), default='')
    organization = db.Column(db.String(160), default='')
    active = db.Column(db.Boolean, default=True)

class Appointment(db.Model):
    assignment_visit_id = db.Column(db.String(36), db.ForeignKey('assignment_visit.id'), index=True)
    assignment_special_code = db.Column(db.String(80), default='')
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    procedure_id = db.Column(db.Integer, db.ForeignKey('procedure.id'), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'))
    order_id = db.Column(
        db.Integer,
        db.ForeignKey('order.id'),
        unique=True,
        index=True,
    )
    scheduled = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(30), default='BOOKED')
    source = db.Column(db.String(40), default='CALL_CENTER')
    notes = db.Column(db.Text, default='')
    created_by = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    checked_in_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    confirmed_at = db.Column(db.DateTime)
    duration_min = db.Column(db.Integer, default=20)
    priority = db.Column(db.String(20), default='NORMAL')
    waiting_list = db.Column(db.Boolean, default=False)
    patient = db.relationship('Patient')
    branch = db.relationship('Branch')
    procedure = db.relationship('Procedure')
    device = db.relationship('Device', foreign_keys=[device_id])
    order = db.relationship(
        'Order',
        back_populates='appointment',
        foreign_keys=[order_id],
    )

class Order(db.Model):
    assignment_visit_id = db.Column(db.String(36), db.ForeignKey('assignment_visit.id'), index=True)
    assignment_special_code = db.Column(db.String(80), default='')
    id = db.Column(db.Integer, primary_key=True)
    accession = db.Column(db.String(40), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    modality = db.Column(db.String(8), nullable=False)
    procedure = db.Column(db.String(120), nullable=False)
    station_ae = db.Column(db.String(40))
    scheduled = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(30), default='REGISTERED')
    patient = db.relationship('Patient')
    report = db.relationship('Report', backref='order', uselist=False, cascade='all,delete-orphan')
    appointment = db.relationship(
        'Appointment',
        back_populates='order',
        uselist=False,
        foreign_keys='Appointment.order_id',
    )

    procedure_id = db.Column(db.Integer, db.ForeignKey('procedure.id'))
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'))
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    referring_doctor_id = db.Column(db.Integer, db.ForeignKey('referring_doctor.id'))
    gross_price = db.Column(db.Float, default=0)
    contract_price = db.Column(db.Float, default=0)
    patient_share = db.Column(db.Float, default=0)
    company_share = db.Column(db.Float, default=0)
    paid_amount = db.Column(db.Float, default=0)
    report_delivered = db.Column(db.Boolean, default=False)
    images_delivered = db.Column(db.Boolean, default=False)
    report_delivered_at = db.Column(db.DateTime)
    images_delivered_at = db.Column(db.DateTime)
    approval_no = db.Column(db.String(80), default='')
    created_by = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    proc = db.relationship('Procedure', foreign_keys=[procedure_id])
    branch = db.relationship('Branch', foreign_keys=[branch_id])
    device = db.relationship('Device', foreign_keys=[device_id])
    contract = db.relationship('Contract', foreign_keys=[contract_id])
    referring_doctor = db.relationship('ReferringDoctor', foreign_keys=[referring_doctor_id])
    priority = db.Column(db.String(20), default='ROUTINE')
    assigned_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assigned_at = db.Column(db.DateTime)
    assigned_doctor = db.relationship('User', foreign_keys=[assigned_doctor_id])
    exam_status = db.Column(db.String(30), default='ORDERED')
    exam_started_at = db.Column(db.DateTime)
    exam_completed_at = db.Column(db.DateTime)
    pacs_image_count = db.Column(db.Integer, default=0)
    pacs_status = db.Column(db.String(30), default='WAITING')
    pacs_last_seen_at = db.Column(db.DateTime)
    pacs_last_change_at = db.Column(db.DateTime)
    pacs_study_id = db.Column(db.String(120), default='')

    # Canonical DICOM Study Instance UID.
    # Orthanc pacs_study_id is an internal UUID and must not be used
    # as the DICOM StudyInstanceUID for OHIF/DICOMweb.
    study_instance_uid = db.Column(
        db.String(180),
        default='',
        index=True
    )

class InsuranceApprovalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey('order.id'),
        nullable=False,
        index=True
    )

    # AUTO / MANUAL / TELEGRAM / EMAIL
    method = db.Column(db.String(30), default='MANUAL', index=True)

    # NOT_REQUIRED / REQUIRED / SUBMITTED / PENDING /
    # APPROVED / REJECTED / NEED_INFO / ERROR
    status = db.Column(db.String(30), default='REQUIRED', index=True)

    approval_no = db.Column(db.String(120), default='', index=True)

    payer_name = db.Column(db.String(180), default='')
    member_no = db.Column(db.String(120), default='')

    requested_at = db.Column(db.DateTime)
    submitted_at = db.Column(db.DateTime)
    decided_at = db.Column(db.DateTime)

    last_checked_at = db.Column(db.DateTime)
    next_check_at = db.Column(db.DateTime)

    notes = db.Column(db.Text, default='')
    last_error = db.Column(db.Text, default='')

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        index=True
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    order = db.relationship(
        'Order',
        foreign_keys=[order_id]
    )

    creator = db.relationship(
        'User',
        foreign_keys=[created_by]
    )

class InsuranceApprovalEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    approval_request_id = db.Column(
        db.Integer,
        db.ForeignKey('insurance_approval_request.id'),
        nullable=False,
        index=True
    )

    event_type = db.Column(
        db.String(60),
        nullable=False,
        index=True
    )

    old_status = db.Column(db.String(30), default='')
    new_status = db.Column(db.String(30), default='')

    message = db.Column(db.Text, default='')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        index=True
    )

    approval_request = db.relationship(
        'InsuranceApprovalRequest',
        foreign_keys=[approval_request_id]
    )

    user = db.relationship(
        'User',
        foreign_keys=[user_id]
    )

class InsurancePortalAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    branch_id = db.Column(
        db.Integer,
        db.ForeignKey('branch.id'),
        nullable=False,
        index=True
    )

    payer_name = db.Column(
        db.String(180),
        nullable=False,
        index=True
    )

    portal_url = db.Column(db.String(500), default='')
    login_url = db.Column(db.String(500), default='')
    portal_type = db.Column(db.String(40), default='WEB')

    username = db.Column(db.String(180), default='')

    # Passwords are NOT stored in plaintext.
    # Example: INSURANCE_AXA_MAIN_PASSWORD
    credential_ref = db.Column(db.String(255), default='')

    requires_otp = db.Column(db.Boolean, default=False)
    workflow_mode = db.Column(db.String(40), default='MANUAL')

    login_notes = db.Column(db.Text, default='')
    workflow_notes = db.Column(db.Text, default='')
    training_notes = db.Column(db.Text, default='')

    selectors_json = db.Column(db.Text, default='{}')
    automation_config_json = db.Column(db.Text, default='{}')

    last_success_at = db.Column(db.DateTime)
    last_error_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text, default='')

    enabled = db.Column(db.Boolean, default=False, index=True)

    telegram_enabled = db.Column(db.Boolean, default=False)
    email_enabled = db.Column(db.Boolean, default=False)
    automation_enabled = db.Column(db.Boolean, default=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    branch = db.relationship(
        'Branch',
        foreign_keys=[branch_id]
    )

    __table_args__ = (
        db.UniqueConstraint(
            'branch_id',
            'payer_name',
            name='uq_insurance_portal_branch_payer'
        ),
    )

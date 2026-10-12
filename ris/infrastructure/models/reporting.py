"""Persisted schema definitions; no web/application initialization."""
from datetime import datetime, date
import json
from infrastructure.extensions import db

class StudioTemplate(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    template_type=db.Column(db.String(40),nullable=False,index=True)
    name=db.Column(db.String(180),nullable=False); scope=db.Column(db.String(40),default='GLOBAL')
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id')); owner_user_id=db.Column(db.Integer,db.ForeignKey('user.id'))
    version_no=db.Column(db.Integer,default=1); status=db.Column(db.String(20),default='DRAFT')
    layout_json=db.Column(db.Text,default='{}'); notes=db.Column(db.Text,default='')
    created_by=db.Column(db.Integer,db.ForeignKey('user.id')); created_at=db.Column(db.DateTime,default=datetime.utcnow)
    published_at=db.Column(db.DateTime)

class StudioTemplateVersion(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    template_id=db.Column(db.Integer,db.ForeignKey('studio_template.id'),nullable=False,index=True)
    version_no=db.Column(db.Integer,nullable=False); snapshot_json=db.Column(db.Text,nullable=False)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id')); created_at=db.Column(db.DateTime,default=datetime.utcnow)

class DoctorWordTemplate(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    owner_user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    name=db.Column(db.String(180),nullable=False); modality=db.Column(db.String(30),default='')
    procedure_id=db.Column(db.Integer,db.ForeignKey('procedure.id')); visibility=db.Column(db.String(30),default='PERSONAL')
    file_path=db.Column(db.String(600),nullable=False); original_name=db.Column(db.String(255),default='')
    active=db.Column(db.Boolean,default=True); created_at=db.Column(db.DateTime,default=datetime.utcnow)

class AIProviderSetting(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    provider_key=db.Column(db.String(40),unique=True,nullable=False,index=True)
    enabled=db.Column(db.Boolean,default=False,index=True)
    base_url=db.Column(db.String(500),default='')
    model_name=db.Column(db.String(180),default='')
    timeout_seconds=db.Column(db.Integer,default=60)
    updated_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class AIDraftReport(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    provider_key=db.Column(db.String(40),default='')
    model_name=db.Column(db.String(180),default='')
    input_context=db.Column(db.Text,default='')
    findings_draft=db.Column(db.Text,default='')
    impression_draft=db.Column(db.Text,default='')
    comparison_draft=db.Column(db.Text,default='')
    safety_notes=db.Column(db.Text,default='')
    status=db.Column(db.String(30),default='GENERATED',index=True)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    reviewed_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    reviewed_at=db.Column(db.DateTime)
    order=db.relationship('Order',foreign_keys=[order_id])

class ExternalReportingSetting(db.Model):
    __tablename__='external_reporting_setting'
    id=db.Column(db.Integer,primary_key=True)
    enabled=db.Column(db.Boolean,nullable=False,default=False)
    updated_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    updated_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow,onupdate=datetime.utcnow)

class ExternalReportingCenter(db.Model):
    __tablename__='external_reporting_center'
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(40),unique=True,nullable=False,index=True)
    name=db.Column(db.String(160),nullable=False)
    ae_title=db.Column(db.String(80),unique=True,nullable=False,index=True)
    receiving_enabled=db.Column(db.Boolean,nullable=False,default=False)
    assignment_enabled=db.Column(db.Boolean,nullable=False,default=False)
    auto_queue=db.Column(db.Boolean,nullable=False,default=False)
    default_priority=db.Column(db.String(20),nullable=False,default='ROUTINE')
    required_documents=db.Column(db.Boolean,nullable=False,default=False)
    billing_enabled=db.Column(db.Boolean,nullable=False,default=False)
    billing_contract_id=db.Column(db.Integer,db.ForeignKey('contract.id'),index=True)
    default_report_fee=db.Column(db.Float,nullable=False,default=0)
    active=db.Column(db.Boolean,nullable=False,default=True,index=True)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    updated_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow,onupdate=datetime.utcnow)
    billing_contract=db.relationship('Contract',foreign_keys=[billing_contract_id])

class ExternalCenterDoctor(db.Model):
    __tablename__='external_center_doctor'
    id=db.Column(db.Integer,primary_key=True)
    center_id=db.Column(db.Integer,db.ForeignKey('external_reporting_center.id'),nullable=False,index=True)
    doctor_user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    active=db.Column(db.Boolean,nullable=False,default=True,index=True)
    center=db.relationship('ExternalReportingCenter',foreign_keys=[center_id])
    doctor=db.relationship('User',foreign_keys=[doctor_user_id])
    __table_args__=(db.UniqueConstraint('center_id','doctor_user_id',name='uq_external_center_doctor'),)

class ExternalIntakeCase(db.Model):
    __tablename__='external_intake_case'
    id=db.Column(db.Integer,primary_key=True)
    center_id=db.Column(db.Integer,db.ForeignKey('external_reporting_center.id'),nullable=False,index=True)
    inbox_id=db.Column(db.Integer,db.ForeignKey('pacs_study_inbox.id'),unique=True,nullable=False,index=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),unique=True,index=True)
    status=db.Column(db.String(30),nullable=False,default='RECEIVED',index=True)
    # RECEIVED/HOLD/QUEUED/REJECTED
    review_note=db.Column(db.String(500),nullable=False,default='')
    expected_patient_id=db.Column(db.String(80),nullable=False,default='')
    expected_patient_name=db.Column(db.String(180),nullable=False,default='')
    expected_dob=db.Column(db.String(8),nullable=False,default='')
    expected_sex=db.Column(db.String(1),nullable=False,default='')
    expected_accession=db.Column(db.String(120),nullable=False,default='')
    dicom_patient_id=db.Column(db.String(80),nullable=False,default='')
    dicom_patient_name=db.Column(db.String(180),nullable=False,default='')
    dicom_dob=db.Column(db.String(8),nullable=False,default='')
    dicom_sex=db.Column(db.String(1),nullable=False,default='')
    dicom_accession=db.Column(db.String(120),nullable=False,default='')
    demographic_status=db.Column(db.String(30),nullable=False,default='NOT_CHECKED',index=True)
    demographic_score=db.Column(db.Float,nullable=False,default=0)
    demographic_checks_json=db.Column(db.Text,nullable=False,default='[]')
    demographic_facts_sha256=db.Column(db.String(64),nullable=False,default='')
    demographic_verified_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    demographic_verified_at=db.Column(db.DateTime)
    demographic_override_approved=db.Column(db.Boolean,nullable=False,default=False)
    demographic_override_reason=db.Column(db.String(500),nullable=False,default='')
    demographic_override_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    demographic_override_at=db.Column(db.DateTime)
    demographic_override_facts_sha256=db.Column(db.String(64),nullable=False,default='')
    reviewed_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    reviewed_at=db.Column(db.DateTime)
    queued_at=db.Column(db.DateTime)
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow,index=True)
    center=db.relationship('ExternalReportingCenter',foreign_keys=[center_id])
    inbox=db.relationship('PacsStudyInbox',foreign_keys=[inbox_id])
    order=db.relationship('Order',foreign_keys=[order_id])

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True, nullable=False)
    status = db.Column(db.String(20), default='UNREPORTED')
    findings = db.Column(db.Text, default='')
    impression = db.Column(db.Text, default='')
    radiologist = db.Column(db.String(120), default='')
    docx_path = db.Column(db.String(500))
    pdf_path = db.Column(db.String(500))
    source_path = db.Column(db.String(500))
    source_type = db.Column(db.String(20), default='DOCX')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finalized_at = db.Column(db.DateTime)
    verified_by = db.Column(db.String(160), default='')
    verified_at = db.Column(db.DateTime)
    second_verified_by = db.Column(db.String(160), default='')
    second_verified_at = db.Column(db.DateTime)
    finalized_by = db.Column(db.String(160), default='')
    addendum_no = db.Column(db.Integer, default=0)

class ReportVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('report.id'), nullable=False, index=True)
    accession = db.Column(db.String(40), nullable=False, index=True)
    version_no = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)
    findings = db.Column(db.Text, default='')
    impression = db.Column(db.Text, default='')
    radiologist = db.Column(db.String(120), default='')
    docx_path = db.Column(db.String(500))
    pdf_path = db.Column(db.String(500))
    source_path = db.Column(db.String(500))
    source_type = db.Column(db.String(20), default='DOCX')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_by = db.Column(db.Integer)
    created_role = db.Column(db.String(60), default='')
    change_summary = db.Column(db.String(500), default='')
    sha256 = db.Column(db.String(64), default='')
    file_size = db.Column(db.Integer, default=0)
    signature = db.Column(db.Text)
    signature_algorithm = db.Column(db.String(50))
    signing_key_id = db.Column(db.Integer)
    signed_by_user_id = db.Column(db.Integer)
    signed_by_name = db.Column(db.String(180))
    signed_at = db.Column(db.DateTime)
    signature_status = db.Column(db.String(30))
    signed_payload_sha256 = db.Column(db.String(64))
    previous_version_sha256 = db.Column(db.String(64))

    # Unified clinical report version safety metadata.
    status = db.Column(db.String(30), default='DRAFT', nullable=False)
    editor_type = db.Column(db.String(30), default='UNKNOWN', nullable=False)
    base_version_no = db.Column(db.Integer)

    # Idempotency token supplied per explicit clinical commit.
    # A network retry must return the existing version rather
    # than creating another clinical version.
    commit_id = db.Column(db.String(36))
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    verified_at = db.Column(db.DateTime)

    # Finalization locks this VERIFIED version.
    # Clinical content remains immutable.
    finalized_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )
    finalized_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint(
            'report_id',
            'version_no',
            name='uq_report_version_report_version_no'
        ),
    )

class ReportEditLease(db.Model):
    __tablename__ = 'report_edit_lease'
    __table_args__ = (
        db.UniqueConstraint(
            'order_id',
            name='uq_report_edit_lease_order_id',
        ),
        db.Index(
            'ix_report_edit_lease_expires_at',
            'expires_at',
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    order_id = db.Column(
        db.Integer,
        db.ForeignKey('order.id'),
        nullable=False,
    )
    report_id = db.Column(
        db.Integer,
        db.ForeignKey('report.id'),
        nullable=False,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False,
    )
    editor_type = db.Column(
        db.String(32),
        nullable=False,
    )
    lease_token_hash = db.Column(
        db.String(80),
        nullable=False,
    )
    acquired_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )
    renewed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )
    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

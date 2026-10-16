"""Persisted schema definitions; no web/application initialization."""
from datetime import datetime, date
import json
from infrastructure.extensions import db

class DictionaryEntry(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    key=db.Column(db.String(160),unique=True,nullable=False,index=True)
    module=db.Column(db.String(80),default='GLOBAL')
    label_en=db.Column(db.String(255),nullable=False,default='')
    label_ar=db.Column(db.String(255),nullable=False,default='')
    active=db.Column(db.Boolean,default=True)

class RibbonAction(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    action_key=db.Column(db.String(100),unique=True,nullable=False,index=True)
    label_en=db.Column(db.String(120),nullable=False)
    label_ar=db.Column(db.String(120),default='')
    icon=db.Column(db.String(40),default='•')
    route_name=db.Column(db.String(120),nullable=False)
    required_permission=db.Column(db.String(120),default='')
    context=db.Column(db.String(40),default='GLOBAL')
    order_no=db.Column(db.Integer,default=100)
    active=db.Column(db.Boolean,default=True)

class UserRibbonAction(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    ribbon_action_id=db.Column(db.Integer,db.ForeignKey('ribbon_action.id'),nullable=False,index=True)
    order_no=db.Column(db.Integer,default=100)
    visible=db.Column(db.Boolean,default=True)
    user=db.relationship('User',foreign_keys=[user_id])
    action=db.relationship('RibbonAction',foreign_keys=[ribbon_action_id])
    __table_args__=(db.UniqueConstraint('user_id','ribbon_action_id',name='uq_user_ribbon_action'),)

class StudioShortcut(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    title_en=db.Column(db.String(120),nullable=False)
    title_ar=db.Column(db.String(120),default='')
    icon=db.Column(db.String(80),default='link')
    accent=db.Column(db.String(30),default='blue')
    target_type=db.Column(db.String(30),default='INTERNAL') # INTERNAL/URL
    target=db.Column(db.String(500),nullable=False)
    placement=db.Column(db.String(40),default='DASHBOARD',index=True) # DASHBOARD/ORDER/PATIENT/DOCTOR/GLOBAL
    open_mode=db.Column(db.String(20),default='SAME') # SAME/NEW
    size=db.Column(db.String(20),default='MEDIUM')
    sort_order=db.Column(db.Integer,default=100,index=True)
    permission_code=db.Column(db.String(120),default='')
    role_code=db.Column(db.String(80),default='')
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    active=db.Column(db.Boolean,default=True,index=True)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    branch=db.relationship('Branch')
    user=db.relationship('User',foreign_keys=[user_id])

class CompanyLegalProfile(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),unique=True,index=True)
    legal_name=db.Column(db.String(200),default=''); commercial_register=db.Column(db.String(120),default='')
    tax_card=db.Column(db.String(120),default=''); tax_number=db.Column(db.String(120),default='')
    phone1=db.Column(db.String(80),default=''); phone2=db.Column(db.String(80),default='')
    email=db.Column(db.String(180),default=''); website=db.Column(db.String(180),default='')
    address=db.Column(db.String(400),default=''); logo_path=db.Column(db.String(500),default='')
    receipt_note_ar=db.Column(db.Text,default=''); receipt_note_en=db.Column(db.Text,default='')

class QARun(db.Model):
    __tablename__='qa_run'

    id=db.Column(db.Integer,primary_key=True)
    run_type=db.Column(db.String(40),default='FULL',index=True)
    status=db.Column(db.String(30),default='PENDING',index=True)

    release_name=db.Column(db.String(120),default='')
    environment=db.Column(db.String(40),default='PRODUCTION')

    total_tests=db.Column(db.Integer,default=0)
    passed_tests=db.Column(db.Integer,default=0)
    failed_tests=db.Column(db.Integer,default=0)
    critical_tests=db.Column(db.Integer,default=0)
    warning_tests=db.Column(db.Integer,default=0)

    external_execution_id=db.Column(db.String(180),default='',index=True)

    started_by=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    started_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    finished_at=db.Column(db.DateTime)

    summary_json=db.Column(db.Text,default='{}')
    error_text=db.Column(db.Text,default='')

class QATestResult(db.Model):
    __tablename__='qa_test_result'

    id=db.Column(db.Integer,primary_key=True)
    run_id=db.Column(db.Integer,db.ForeignKey('qa_run.id'),nullable=False,index=True)

    test_key=db.Column(db.String(120),nullable=False,index=True)
    category=db.Column(db.String(80),default='',index=True)
    title=db.Column(db.String(220),default='')

    status=db.Column(db.String(20),default='PENDING',index=True)
    severity=db.Column(db.String(20),default='NORMAL',index=True)

    expected=db.Column(db.Text,default='')
    actual=db.Column(db.Text,default='')
    details_json=db.Column(db.Text,default='{}')
    error_text=db.Column(db.Text,default='')

    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),index=True)

    started_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    finished_at=db.Column(db.DateTime)

class QARemediationAction(db.Model):
    __tablename__='qa_remediation_action'

    id=db.Column(db.Integer,primary_key=True)

    run_id=db.Column(db.Integer,db.ForeignKey('qa_run.id'),index=True)
    test_result_id=db.Column(db.Integer,db.ForeignKey('qa_test_result.id'),index=True)

    action_key=db.Column(db.String(120),nullable=False,index=True)
    status=db.Column(db.String(30),default='PENDING',index=True)

    requested_by=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    requested_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    completed_at=db.Column(db.DateTime)

    details_json=db.Column(db.Text,default='{}')
    error_text=db.Column(db.Text,default='')

class SavedSearchFilter(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
    name=db.Column(db.String(160),nullable=False)
    page_key=db.Column(db.String(80),default='GLOBAL',index=True)
    filter_json=db.Column(db.Text,default='{}')
    is_default=db.Column(db.Boolean,default=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)

class LabelTemplate(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),nullable=False)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    width_mm=db.Column(db.Integer,default=50)
    height_mm=db.Column(db.Integer,default=30)
    layout_json=db.Column(db.Text,default='{}')
    active=db.Column(db.Boolean,default=True,index=True)
    is_default=db.Column(db.Boolean,default=False)

class PrinterProfile(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),nullable=False)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),index=True)
    workstation_code=db.Column(db.String(120),default='',index=True)
    document_type=db.Column(db.String(30),nullable=False,index=True) # RECEIPT/LABEL/REPORT/A4
    printer_name=db.Column(db.String(255),default='')
    paper_size=db.Column(db.String(40),default='A4')
    copies=db.Column(db.Integer,default=1)
    auto_open_print_dialog=db.Column(db.Boolean,default=True)
    active=db.Column(db.Boolean,default=True,index=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
    branch=db.relationship('Branch')
    user=db.relationship('User')

class EventOutbox(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    event_type=db.Column(db.String(80),nullable=False,index=True)
    entity_type=db.Column(db.String(80),nullable=False,default='')
    entity_id=db.Column(db.String(120),nullable=False,default='')
    payload_json=db.Column(db.Text,default='{}')
    status=db.Column(db.String(20),default='PENDING',index=True)
    attempts=db.Column(db.Integer,default=0)
    last_error=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    processed_at=db.Column(db.DateTime)

class CompanyProfile(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name_en=db.Column(db.String(180),default='RIS Operations')
    name_ar=db.Column(db.String(180),default='نظام الأشعة')
    address_en=db.Column(db.String(255),default='')
    address_ar=db.Column(db.String(255),default='')
    phone=db.Column(db.String(80),default='')
    mobile=db.Column(db.String(80),default='')
    email=db.Column(db.String(180),default='')
    website=db.Column(db.String(180),default='')
    logo_path=db.Column(db.String(500),default='')
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class StickerTemplate(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(120),nullable=False,default='Patient Sticker Bilingual')
    active=db.Column(db.Boolean,default=True)
    is_default=db.Column(db.Boolean,default=False)
    width_mm=db.Column(db.Float,default=70)
    height_mm=db.Column(db.Float,default=45)
    bilingual=db.Column(db.Boolean,default=True)
    show_logo=db.Column(db.Boolean,default=True)
    show_qr=db.Column(db.Boolean,default=True)
    show_barcode=db.Column(db.Boolean,default=True)
    fields_json=db.Column(db.Text,default='[]')
    labels_json=db.Column(db.Text,default='{}')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class StorageLocation(db.Model):
    """Logical storage target.

    The application stores a stable code and OS-visible mount path instead of
    vendor-specific logic. Dell EMC, QNAP, TrueNAS, SAN and cloud gateways are
    therefore interchangeable when mounted/exposed through the selected
    protocol. Never store storage credentials in this table.
    """
    __tablename__='storage_location'
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(40),unique=True,nullable=False)
    label=db.Column(db.String(160),nullable=False)
    path=db.Column(db.String(700),nullable=False)
    storage_type=db.Column(db.String(30),default='LOCAL') # LOCAL/PACS/ARCHIVE/BACKUP
    protocol=db.Column(db.String(30),default='LOCAL') # LOCAL/NFS/SMB/ISCSI/S3/GATEWAY
    role=db.Column(db.String(30),default='PRIMARY') # PRIMARY/ARCHIVE/BACKUP/DR
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    company_code=db.Column(db.String(60),default='',index=True)
    vendor=db.Column(db.String(80),default='')
    endpoint=db.Column(db.String(255),default='')
    mount_source=db.Column(db.String(500),default='')
    filesystem=db.Column(db.String(40),default='')
    priority=db.Column(db.Integer,default=100)
    read_only=db.Column(db.Boolean,default=False)
    capacity_bytes=db.Column(db.BigInteger,default=0)
    free_bytes=db.Column(db.BigInteger,default=0)
    health_status=db.Column(db.String(30),default='UNKNOWN',index=True)
    last_health_at=db.Column(db.DateTime)
    notes=db.Column(db.Text,default='')
    active=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    branch=db.relationship('Branch',foreign_keys=[branch_id])

class ReplicationNode(db.Model):
    """A primary/DR endpoint participating in data or configuration replication."""
    __tablename__='replication_node'
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(60),unique=True,nullable=False,index=True)
    name=db.Column(db.String(160),nullable=False)
    node_role=db.Column(db.String(30),default='DR') # PRIMARY/DR/WITNESS/ARCHIVE
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),index=True)
    company_code=db.Column(db.String(60),default='',index=True)
    host=db.Column(db.String(255),default='')
    site=db.Column(db.String(160),default='')
    active=db.Column(db.Boolean,default=True)
    health_status=db.Column(db.String(30),default='UNKNOWN',index=True)
    last_seen_at=db.Column(db.DateTime)
    notes=db.Column(db.Text,default='')
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    branch=db.relationship('Branch',foreign_keys=[branch_id])

class ReplicationPolicy(db.Model):
    """Declarative DR policy. Execution is performed by external/worker services.

    Secrets and destructive failover commands are intentionally not persisted
    here. The table stores topology, desired RPO/RTO and transport metadata.
    """
    __tablename__='replication_policy'
    id=db.Column(db.Integer,primary_key=True)
    code=db.Column(db.String(60),unique=True,nullable=False,index=True)
    name=db.Column(db.String(180),nullable=False)
    source_node_id=db.Column(db.Integer,db.ForeignKey('replication_node.id'),nullable=False)
    target_node_id=db.Column(db.Integer,db.ForeignKey('replication_node.id'),nullable=False)
    data_scope=db.Column(db.String(40),default='PACS') # PACS/DATABASE/REPORTS/ATTACHMENTS/CONFIG/ALL
    transport=db.Column(db.String(50),default='RSYNC') # RSYNC/STORAGE_NATIVE/POSTGRES_STREAMING/DICOM_FORWARD/S3_REPLICATION
    mode=db.Column(db.String(30),default='ASYNC') # ASYNC/SYNC/SCHEDULED
    source_storage_id=db.Column(db.Integer,db.ForeignKey('storage_location.id'))
    target_storage_id=db.Column(db.Integer,db.ForeignKey('storage_location.id'))
    rpo_minutes=db.Column(db.Integer,default=15)
    rto_minutes=db.Column(db.Integer,default=60)
    schedule=db.Column(db.String(120),default='')
    active=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    source_node=db.relationship('ReplicationNode',foreign_keys=[source_node_id])
    target_node=db.relationship('ReplicationNode',foreign_keys=[target_node_id])
    source_storage=db.relationship('StorageLocation',foreign_keys=[source_storage_id])
    target_storage=db.relationship('StorageLocation',foreign_keys=[target_storage_id])

class ReplicationState(db.Model):
    __tablename__='replication_state'
    id=db.Column(db.Integer,primary_key=True)
    policy_id=db.Column(db.Integer,db.ForeignKey('replication_policy.id'),nullable=False,index=True)
    status=db.Column(db.String(30),default='UNKNOWN',index=True) # HEALTHY/LAGGING/OFFLINE/RESYNCING/ERROR
    last_success_at=db.Column(db.DateTime)
    last_check_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    lag_seconds=db.Column(db.Integer,default=0)
    pending_items=db.Column(db.BigInteger,default=0)
    pending_bytes=db.Column(db.BigInteger,default=0)
    checkpoint=db.Column(db.String(500),default='')
    last_error=db.Column(db.Text,default='')
    policy=db.relationship('ReplicationPolicy',foreign_keys=[policy_id])

class FailoverEvent(db.Model):
    __tablename__='failover_event'
    id=db.Column(db.Integer,primary_key=True)
    policy_id=db.Column(db.Integer,db.ForeignKey('replication_policy.id'),nullable=False,index=True)
    action=db.Column(db.String(30),nullable=False) # PLAN/PROMOTE/FAILBACK/TEST
    status=db.Column(db.String(30),default='PLANNED')
    requested_by=db.Column(db.Integer)
    requested_at=db.Column(db.DateTime,default=datetime.utcnow,index=True)
    completed_at=db.Column(db.DateTime)
    notes=db.Column(db.Text,default='')
    policy=db.relationship('ReplicationPolicy',foreign_keys=[policy_id])

class CloudBackupConfig(db.Model):
    __tablename__='cloud_backup_config'
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),nullable=False)
    provider=db.Column(db.String(40),default='RCLONE')
    rclone_remote=db.Column(db.String(120),default='')
    remote_root=db.Column(db.String(500),default='')
    include_reports=db.Column(db.Boolean,default=True)
    include_attachments=db.Column(db.Boolean,default=True)
    include_database=db.Column(db.Boolean,default=True)
    include_pacs=db.Column(db.Boolean,default=False)
    schedule_hour=db.Column(db.Integer,default=2)
    active=db.Column(db.Boolean,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)

class BackupRun(db.Model):
    __tablename__='backup_run'
    id=db.Column(db.Integer,primary_key=True)
    config_id=db.Column(db.Integer,db.ForeignKey('cloud_backup_config.id'))
    status=db.Column(db.String(30),default='RUNNING',index=True)
    started_at=db.Column(db.DateTime,default=datetime.utcnow)
    completed_at=db.Column(db.DateTime)
    reports_files=db.Column(db.Integer,default=0)
    attachments_files=db.Column(db.Integer,default=0)
    database_file=db.Column(db.String(700),default='')
    pacs_files=db.Column(db.Integer,default=0)
    last_error=db.Column(db.Text,default='')
    config=db.relationship('CloudBackupConfig',foreign_keys=[config_id])

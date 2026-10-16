"""Revision schema copies the canonical report contracts exactly once."""
from datetime import datetime
from sqlalchemy import UniqueConstraint
from infrastructure.extensions import db
from infrastructure.models.reporting import Report, ReportVersion

summary={c.name:c._copy() for c in Report.__table__.columns}
summary['order_id'].unique=False
summary.update({
        '__tablename__':'report_revision',
        'original_report_id':db.Column(db.Integer,db.ForeignKey('report.id'),nullable=False,index=True),
        'original_version_id':db.Column(db.Integer,db.ForeignKey('report_version.id'),nullable=False),
        'original_sha256':db.Column(db.String(64),nullable=False),
        'base_revision_id':db.Column(db.Integer,db.ForeignKey('report_revision.id')),
        'base_sha256':db.Column(db.String(64),nullable=False),
        'revision_no':db.Column(db.Integer,nullable=False),
        'kind':db.Column(db.String(20),nullable=False),
        'reason':db.Column(db.Text,nullable=False),
        'requested_by':db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False),
        'requested_at':db.Column(db.DateTime,nullable=False,default=datetime.utcnow),
        'reviewed_by':db.Column(db.Integer,db.ForeignKey('user.id')),
        'reviewed_at':db.Column(db.DateTime),
        'review_reason':db.Column(db.Text,default=''),
        'doctor_id':db.Column(db.Integer,db.ForeignKey('user.id')),
        'active_order_id':db.Column(db.Integer,db.ForeignKey('order.id'),unique=True),
        'lease_hash':db.Column(db.String(64),default=''),
        'lease_expires_at':db.Column(db.DateTime),
        'editor_key':db.Column(db.String(128),default=''),
        'working_path':db.Column(db.String(500)),
        'forcesave_nonce':db.Column(db.String(36),default=''),
        '__table_args__':(UniqueConstraint('order_id','revision_no',name='uq_report_revision_order_no'),),
    })
Revision=type('ReportRevision',(db.Model,),summary)
columns={c.name:c._copy() for c in ReportVersion.__table__.columns if c.name!='report_id'}
columns.update({
        '__tablename__':'report_revision_version',
        'report_id':db.Column(db.Integer,db.ForeignKey('report_revision.id'),nullable=False,index=True),
        '__table_args__':(UniqueConstraint('report_id','version_no',name='uq_report_revision_version_no'),
                         UniqueConstraint('report_id','commit_id',name='uq_report_revision_commit')),
    })
Version=type('ReportRevisionVersion',(db.Model,),columns)

ReportRevision = Revision
ReportRevisionVersion = Version

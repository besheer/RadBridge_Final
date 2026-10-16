"""Radiotherapy schema, registered once independently of web instances."""
from datetime import datetime
from infrastructure.extensions import db

class RTCourse(db.Model):
    __tablename__='rt_course'
    id=db.Column(db.Integer,primary_key=True)
    primary_order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False)
    patient_id=db.Column(db.Integer,db.ForeignKey('patient.id'),nullable=False)
    branch_id=db.Column(db.Integer,db.ForeignKey('branch.id'),nullable=False)
    reference=db.Column(db.String(100),unique=True,nullable=False)
    status=db.Column(db.String(20),nullable=False,default='DRAFT')
    version=db.Column(db.Integer,nullable=False,default=1)
    created_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    created_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    patient=db.relationship('Patient');order=db.relationship('Order');branch=db.relationship('Branch')
    __table_args__=(db.CheckConstraint("status IN ('DRAFT','ACTIVE','PAUSED','COMPLETED','CANCELLED')"),)

class RTPlanVersion(db.Model):
    __tablename__='rt_plan_version'
    id=db.Column(db.Integer,primary_key=True)
    course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
    revision=db.Column(db.Integer,nullable=False)
    external_reference=db.Column(db.String(150),nullable=False)
    approved_by=db.Column(db.String(150),nullable=False)
    approved_on=db.Column(db.Date,nullable=False)
    attachment_id=db.Column(db.Integer,db.ForeignKey('attachment.id'))
    target=db.Column(db.Text,nullable=False)
    total_gy=db.Column(db.Numeric(18,6),nullable=False)
    fraction_gy=db.Column(db.Numeric(18,6),nullable=False)
    fractions=db.Column(db.Integer,nullable=False)
    status=db.Column(db.String(20),nullable=False,default='ACTIVE')
    reason=db.Column(db.Text,nullable=False)
    recorded_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    recorded_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    __table_args__=(db.UniqueConstraint('course_id','revision'),db.UniqueConstraint('id','course_id'),db.CheckConstraint('total_gy > 0 AND fraction_gy > 0 AND fractions > 0'),db.CheckConstraint("status IN ('ACTIVE','SUPERSEDED')"))

class RTFraction(db.Model):
    __tablename__='rt_fraction'
    id=db.Column(db.Integer,primary_key=True)
    course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
    plan_id=db.Column(db.Integer,nullable=False)
    number=db.Column(db.Integer,nullable=False)
    attempt=db.Column(db.Integer,nullable=False,default=1)
    scheduled_at=db.Column(db.DateTime,nullable=False)
    device_id=db.Column(db.Integer,db.ForeignKey('device.id'),nullable=False)
    planned_gy=db.Column(db.Numeric(18,6),nullable=False)
    actual_gy=db.Column(db.Numeric(18,6))
    started_at=db.Column(db.DateTime);ended_at=db.Column(db.DateTime)
    status=db.Column(db.String(20),nullable=False,default='SCHEDULED')
    reason=db.Column(db.Text,default='')
    operator_id=db.Column(db.Integer,db.ForeignKey('user.id'))
    completion_key=db.Column(db.String(80));completion_hash=db.Column(db.String(64))
    delivery_reference=db.Column(db.String(150),default='')
    version=db.Column(db.Integer,nullable=False,default=1)
    device=db.relationship('Device')
    __table_args__=(db.UniqueConstraint('course_id','number','attempt'),db.ForeignKeyConstraint(['plan_id','course_id'],['rt_plan_version.id','rt_plan_version.course_id']),db.CheckConstraint("status IN ('SCHEDULED','STARTED','COMPLETED','NOT_GIVEN','CANCELLED')"),db.CheckConstraint('number > 0 AND planned_gy > 0 AND (actual_gy IS NULL OR actual_gy > 0)'),db.CheckConstraint("status != 'COMPLETED' OR (actual_gy IS NOT NULL AND started_at IS NOT NULL AND ended_at IS NOT NULL AND operator_id IS NOT NULL)"),db.CheckConstraint('ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)'))

class RTPetLink(db.Model):
    __tablename__='rt_pet_link'
    id=db.Column(db.Integer,primary_key=True)
    course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False)
    purpose=db.Column(db.String(30),nullable=False)
    reason=db.Column(db.Text,nullable=False)
    linked_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    linked_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    order=db.relationship('Order')
    __table_args__=(db.UniqueConstraint('course_id','order_id'),db.CheckConstraint("purpose IN ('BASELINE','PLANNING_REFERENCE','FOLLOW_UP','OTHER')"))

class RTNote(db.Model):
    __tablename__='rt_note'
    id=db.Column(db.Integer,primary_key=True)
    course_id=db.Column(db.Integer,db.ForeignKey('rt_course.id'),nullable=False)
    fraction_id=db.Column(db.Integer,db.ForeignKey('rt_fraction.id'))
    kind=db.Column(db.String(20),nullable=False)
    body=db.Column(db.Text,nullable=False)
    recorded_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    recorded_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)

class RTConsumable(db.Model):
    __tablename__='rt_consumable'
    id=db.Column(db.Integer,primary_key=True)
    fraction_id=db.Column(db.Integer,db.ForeignKey('rt_fraction.id'),nullable=False)
    name=db.Column(db.String(150),nullable=False)
    quantity=db.Column(db.Numeric(18,6),nullable=False)
    unit=db.Column(db.String(40),nullable=False)
    recorded_by=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    recorded_at=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    __table_args__=(db.CheckConstraint('quantity > 0'),)

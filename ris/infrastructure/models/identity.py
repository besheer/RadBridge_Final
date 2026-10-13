"""Persisted schema definitions; no web/application initialization."""
from datetime import datetime, date
import json
from infrastructure.extensions import db

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, default=True)
    reception_collection_enabled = db.Column(db.Boolean, default=False, nullable=False)

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    permissions_json = db.Column(db.Text, default='[]')
    def permissions(self):
        try: return json.loads(self.permissions_json or '[]')
        except Exception: return []

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'))
    active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=False)
    password_changed_at = db.Column(db.DateTime)
    role = db.relationship('Role')
    branch = db.relationship('Branch')

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(80))
    action = db.Column(db.String(100), nullable=False)
    entity = db.Column(db.String(80))
    entity_id = db.Column(db.String(80))
    details = db.Column(db.Text, default='')
    ip = db.Column(db.String(80), default='')

class UserProfile(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,unique=True,index=True)
    department=db.Column(db.String(80),default='')
    specialty=db.Column(db.String(120),default='')
    default_workspace=db.Column(db.String(120),default='')
    ui_language=db.Column(db.String(10),default='en')
    theme=db.Column(db.String(20),default='light')
    accent=db.Column(db.String(30),default='default')
    density=db.Column(db.String(20),default='comfortable')
    font_scale=db.Column(db.String(20),default='normal')
    sidebar_mode=db.Column(db.String(20),default='expanded')
    settings_json=db.Column(db.Text,default='{}')
    user=db.relationship('User',foreign_keys=[user_id])

class PortalAccessToken(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    order_id=db.Column(db.Integer,db.ForeignKey('order.id'),nullable=False,index=True)
    token=db.Column(db.String(120),unique=True,nullable=False,index=True)
    expires_at=db.Column(db.DateTime,nullable=False)
    revoked=db.Column(db.Boolean,default=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    order=db.relationship('Order',foreign_keys=[order_id])

class DoctorSigningKey(db.Model):
    __tablename__ = 'doctor_signing_key'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    key_id = db.Column(db.String(64), nullable=False, unique=True)
    algorithm = db.Column(db.String(50), nullable=False, default='Ed25519')
    public_key = db.Column(db.Text, nullable=False)
    encrypted_private_key = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime)
    revoked_reason = db.Column(db.String(255))

    user = db.relationship('User', foreign_keys=[user_id])

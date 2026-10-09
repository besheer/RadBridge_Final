from werkzeug.security import generate_password_hash
import app as m

def make_user(code, username):
    role=m.Role.query.filter_by(code=code).first()
    user=m.User(username=username,full_name=username,password_hash=generate_password_hash('secret'),role_id=role.id,active=True)
    m.db.session.add(user);m.db.session.commit();return user

def login(client,user):
    with client.session_transaction() as session:session['uid']=user.id

def test_failed_login_is_audited_without_password(app_ctx):
    client=m.app.test_client();response=client.post('/login',data={'username':'missing-user','password':'never-store-this'})
    assert response.status_code==200
    row=m.AuditLog.query.filter_by(action='LOGIN_FAILED',username='missing-user').order_by(m.AuditLog.id.desc()).first()
    assert row is not None and 'never-store-this' not in (row.details or '')

def test_cancellation_center_permissions_and_reason(app_ctx):
    admin=make_user('SUPER_ADMIN','cancel-admin');reception=make_user('RECEPTION','cancel-reception')
    client=m.app.test_client();login(client,reception);assert client.get('/admin/cancellation-center').status_code==403
    login(client,admin);assert client.get('/admin/cancellation-center').status_code==200

def test_admin_appointment_cancel_writes_reasoned_audit(app_ctx):
    admin=m.User.query.filter_by(username='cancel-admin').first() or make_user('SUPER_ADMIN','cancel-admin')
    patient=m.Patient(patient_id='CANCEL-P1',name='Cancellation Test')
    branch=m.Branch(code='CANCEL-BR',name='Cancel Branch',active=True)
    procedure=m.Procedure(code='CANCEL-PROC',name='Cancel Exam',modality='DX',active=True)
    m.db.session.add_all([patient,branch,procedure]);m.db.session.flush()
    appointment=m.Appointment(patient_id=patient.id,branch_id=branch.id,procedure_id=procedure.id,scheduled=m.datetime.utcnow(),status='BOOKED')
    m.db.session.add(appointment);m.db.session.commit();client=m.app.test_client();login(client,admin)
    assert client.post(f'/admin/cancellation-center/appointments/{appointment.id}/cancel',data={'reason':'Patient requested cancellation'}).status_code==302
    m.db.session.refresh(appointment);assert appointment.status=='CANCELLED'
    row=m.AuditLog.query.filter_by(action='APPOINTMENT_CANCELLED_ADMIN',entity_id=str(appointment.id)).first()
    assert row and 'Patient requested cancellation' in row.details

def test_cancellation_reason_is_required(app_ctx):
    admin=m.User.query.filter_by(username='cancel-admin').first() or make_user('SUPER_ADMIN','cancel-admin')
    appointment=m.Appointment.query.filter_by(status='CANCELLED').first()
    client=m.app.test_client();login(client,admin)
    assert client.post(f'/admin/cancellation-center/appointments/{appointment.id}/cancel',data={'reason':'x'}).status_code==400

def test_audit_center_filters_failed_logins(app_ctx):
    admin=m.User.query.filter_by(username='cancel-admin').first() or make_user('SUPER_ADMIN','cancel-admin')
    client=m.app.test_client();login(client,admin);response=client.get('/admin/audit?action=LOGIN_FAILED')
    assert response.status_code==200 and b'Security & Audit Center' in response.data

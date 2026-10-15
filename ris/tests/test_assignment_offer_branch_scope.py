from datetime import datetime, timedelta
from uuid import uuid4


def fixture(m):
    suffix=uuid4().hex[:8].upper()
    own=m.Branch(code='OFFER'+suffix,name='Offer branch '+suffix)
    other=m.Branch(code='OTHER'+suffix,name='Other branch '+suffix)
    role=m.Role(code='OFFER-'+suffix,name='Branch assignment manager',permissions_json='["assignment.manage"]')
    m.db.session.add_all([own,other,role]);m.db.session.flush()
    actor=m.User(username='offer-manager-'+suffix,full_name='Offer manager',password_hash='test',role=role,branch_id=own.id,active=True)
    doctor=m.User(username='offer-doctor-'+suffix,full_name='Own branch doctor',password_hash='test',role_id=m.Role.query.filter_by(code='RADIOLOGIST').one().id,branch_id=own.id,active=True)
    foreign=m.User(username='foreign-doctor-'+suffix,full_name='Other branch doctor',password_hash='test',role_id=doctor.role_id,branch_id=other.id,active=True)
    patient=m.Patient(patient_id='OFFER-PATIENT-'+suffix,name='Synthetic offer patient')
    m.db.session.add_all([actor,doctor,foreign,patient]);m.db.session.flush()
    order=m.Order(accession='OFFER-'+suffix,patient_id=patient.id,branch_id=own.id,modality='CT',procedure='Synthetic',scheduled=datetime.utcnow(),status='COMPLETED')
    foreign_order=m.Order(accession='OTHER-OFFER-'+suffix,patient_id=patient.id,branch_id=other.id,modality='CT',procedure='Synthetic',scheduled=datetime.utcnow(),status='COMPLETED')
    m.db.session.add_all([order,foreign_order]);m.db.session.commit()
    client=m.app.test_client()
    with client.session_transaction() as state:state['uid']=actor.id
    return actor,doctor,foreign,order,foreign_order,client


def test_branch_offer_start_only_sees_doctors_from_permitted_branch(app_ctx,monkeypatch):
    m=app_ctx
    _,doctor,foreign,order,_,client=fixture(m)
    seen={}
    def fake_offer(target,created_by=None):
        seen['doctors']={u.id for u in m.User.query.join(m.Role).filter(m.Role.code.in_(('RADIOLOGIST','DOCTOR'))).all()}
        seen['order']=target.id
        return None,'NO_CANDIDATE'
    monkeypatch.setattr(m,'offer_next_doctor',fake_offer)

    response=client.post(f'/orders/{order.id}/assignment-offer/start',base_url='https://localhost')

    assert response.status_code==302
    assert seen['order']==order.id
    assert doctor.id in seen['doctors']
    assert foreign.id not in seen['doctors']


def test_branch_offer_start_cannot_target_another_branch(app_ctx,monkeypatch):
    m=app_ctx
    _,_,_,_,foreign_order,client=fixture(m)
    called=[]
    monkeypatch.setattr(m,'offer_next_doctor',lambda *a,**k:called.append(True))

    response=client.post(f'/orders/{foreign_order.id}/assignment-offer/start',base_url='https://localhost')

    assert response.status_code==403
    assert not called


def test_branch_offer_expiry_only_sees_its_branch(app_ctx,monkeypatch):
    m=app_ctx
    _,doctor,foreign,order,foreign_order,client=fixture(m)
    now=datetime.utcnow()
    m.db.session.add_all([
        m.AssignmentOffer(order_id=order.id,doctor_user_id=doctor.id,status='PENDING',offered_at=now-timedelta(minutes=5),expires_at=now-timedelta(minutes=1)),
        m.AssignmentOffer(order_id=foreign_order.id,doctor_user_id=foreign.id,status='PENDING',offered_at=now-timedelta(minutes=5),expires_at=now-timedelta(minutes=1)),
    ]);m.db.session.commit()
    seen={}
    def fake_expire():
        seen['ids']={offer.order_id for offer in m.AssignmentOffer.query.filter_by(status='PENDING').all()}
        return []
    monkeypatch.setattr(m,'expire_assignment_offers',fake_expire)

    response=client.post('/assignment/offers/expire-now',base_url='https://localhost')

    assert response.status_code==302
    assert seen['ids']=={order.id}

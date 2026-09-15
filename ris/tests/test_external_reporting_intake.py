from datetime import datetime
import json
import uuid

import pytest


def unique(prefix):
    return prefix+'-'+uuid.uuid4().hex[:8]


@pytest.fixture
def external_setup(app_ctx,monkeypatch):
    m=app_ctx
    admin_role=m.Role.query.filter_by(code='SUPER_ADMIN').first()
    doctor_role=m.Role.query.filter_by(code='RADIOLOGIST').first()
    tech_role=m.Role.query.filter_by(code='TECHNICIAN').first()
    doctor_role.permissions_json=json.dumps(['reports.view','reports.edit'])
    admin=m.User(username=unique('ext-admin'),full_name='External Admin',password_hash='x',role_id=admin_role.id,active=True)
    doctor=m.User(username=unique('ext-doc'),full_name='External Doctor',password_hash='x',role_id=doctor_role.id,active=True)
    other=m.User(username=unique('other-doc'),full_name='Other Doctor',password_hash='x',role_id=doctor_role.id,active=True)
    tech=m.User(username=unique('ext-tech'),full_name='External Tech',password_hash='x',role_id=tech_role.id,active=True)
    m.db.session.add_all([admin,doctor,other,tech]);m.db.session.flush()
    if not m.Branch.query.filter_by(active=True).first():
        m.db.session.add(m.Branch(code=unique('EXTBR').upper(),name='External test branch',active=True))
    setting=m.external_reporting_setting()
    setting.enabled=True;setting.updated_by=admin.id
    center=m.ExternalReportingCenter(code=unique('CTR').upper(),name='External Center',ae_title=unique('EXTAE').upper(),receiving_enabled=True,assignment_enabled=True,active=True,created_by=admin.id)
    m.db.session.add(center);m.db.session.flush()
    m.db.session.add(m.ExternalCenterDoctor(center_id=center.id,doctor_user_id=doctor.id,active=True))
    inbox=m.PacsStudyInbox(orthanc_study_id=unique('study'),study_instance_uid='1.2.826.'+str(uuid.uuid4().int),pacs_patient_id='REMOTE-1',pacs_patient_name='External^Patient',accession=unique('remote'),modality='DX',study_description='External chest',source_ae=center.ae_title,image_count=2,state='REVIEW_REQUIRED')
    m.db.session.add(inbox);m.db.session.commit()
    monkeypatch.setattr(m,'external_intake_dicom_demographics',lambda row:({
        'patient_id':'REMOTE-1','patient_name':'External^Patient',
        'dob':'19900102','sex':'F','accession':inbox.accession
    },''))
    return m,admin,doctor,other,tech,setting,center,inbox


def login(client,user):
    with client.session_transaction() as session:
        session['uid']=user.id


def set_matching_referral(row):
    row.expected_patient_id='REMOTE-1'
    row.expected_patient_name='External Patient'
    row.expected_dob='19900102'
    row.expected_sex='F'
    row.expected_accession=row.inbox.accession


def test_capture_isolated_and_does_not_create_order_offer_or_assignment(external_setup):
    m,_,_,_,_,_,center,inbox=external_setup
    before=(m.Order.query.count(),m.AssignmentOffer.query.count(),m.CaseAssignment.query.count())
    assert m.capture_external_pacs_studies()==1
    m.db.session.commit()
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    assert row.center_id==center.id and row.status=='RECEIVED' and row.order_id is None
    assert (m.Order.query.count(),m.AssignmentOffer.query.count(),m.CaseAssignment.query.count())==before


def test_unknown_ae_is_not_captured(external_setup):
    m,*_=external_setup
    inbox=m.PacsStudyInbox(orthanc_study_id=unique('unknown-study'),study_instance_uid='1.2.3.'+str(uuid.uuid4().int),source_ae='UNREGISTERED-AE',image_count=1)
    m.db.session.add(inbox);m.db.session.commit()
    m.capture_external_pacs_studies();m.db.session.commit()
    assert m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).first() is None


def test_known_external_ae_never_enters_internal_auto_match(external_setup,monkeypatch):
    m,_,_,_,_,_,center,_=external_setup
    sid=unique('auto-ext-study')
    tags={'study_id':sid,'study_instance_uid':'1.2.840.'+str(uuid.uuid4().int),
          'patient_id':'REMOTE','patient_name':'Remote^Patient','accession':'INTERNAL-LIKE',
          'modality':'DX','study_description':'External study','source_ae':center.ae_title,
          'instances':3,'study_date':'20260914'}
    monkeypatch.setattr(m,'_orthanc_recent_studies',lambda limit:[{'ID':sid}])
    monkeypatch.setattr(m,'_study_tags_extended',lambda study:tags)
    monkeypatch.setattr(m,'strict_pacs_demographic_match',
                        lambda value:(_ for _ in ()).throw(AssertionError('internal matcher called')))
    result=m.pacs_auto_intake_once()
    inbox=m.PacsStudyInbox.query.filter_by(orthanc_study_id=sid).one()
    intake=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    assert result['review_required']==1
    assert inbox.state=='EXTERNAL_INTAKE' and inbox.order_id is None
    assert intake.center_id==center.id and intake.status=='RECEIVED'


def test_master_switch_blocks_capture(external_setup):
    m,_,_,_,_,setting,_,inbox=external_setup
    setting.enabled=False;m.db.session.commit()
    assert m.capture_external_pacs_studies()==0
    assert m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).first() is None


def test_queue_fails_closed_without_doctor_pool(external_setup):
    m,admin,doctor,_,_,_,center,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    m.ExternalCenterDoctor.query.filter_by(center_id=center.id,doctor_user_id=doctor.id).one().active=False
    m.db.session.commit()
    client=m.app.test_client();login(client,admin)
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    response=client.post(f'/admin/external-intake/{row.id}/decision',data={'action':'QUEUE'})
    assert response.status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.status=='RECEIVED' and row.order_id is None


def test_admin_queue_creates_external_order_only_after_decision(external_setup,monkeypatch):
    m,admin,_,_,_,_,center,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    monkeypatch.setattr(m,'offer_next_doctor',lambda order,created_by=None:(None,'OFFERED'))
    client=m.app.test_client();login(client,admin)
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    set_matching_referral(row);m.db.session.commit()
    response=client.post(f'/admin/external-intake/{row.id}/decision',data={'action':'QUEUE'})
    assert response.status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.status=='QUEUED' and row.order_id
    assert row.order.accession==f'E{center.id}I{row.id}'
    assert row.order.pacs_study_id==inbox.orthanc_study_id
    assert row.order.pacs_status=='IMAGES_COMPLETE'
    assert m.AuditLog.query.filter_by(action='EXTERNAL_INTAKE_QUEUE',entity_id=str(row.id)).count()==1


def test_external_order_candidates_are_limited_to_center_pool(external_setup):
    m,_,doctor,other,_,_,center,inbox=external_setup
    patient=m.Patient(patient_id=unique('EXT-P'),name='External',dob='',sex='')
    m.db.session.add(patient);m.db.session.flush()
    order=m.Order(accession=unique('EXT-A'),patient_id=patient.id,modality='DX',procedure='External',scheduled=datetime.utcnow(),status='IMAGES_RECEIVED',exam_status='EXAM_COMPLETED')
    m.db.session.add(order);m.db.session.flush()
    intake=m.ExternalIntakeCase(center_id=center.id,inbox_id=inbox.id,order_id=order.id,status='QUEUED')
    policy=m.AssignmentOfferPolicy(name=unique('policy'),enabled=True,mode='ALL')
    m.db.session.add_all([intake,policy]);m.db.session.commit()
    candidates=m.assignment_candidate_users(order,policy)
    assert doctor in candidates and other not in candidates


def test_internal_order_candidates_remain_unrestricted_by_external_pool(external_setup):
    m,_,doctor,other,_,_,_,_=external_setup
    patient=m.Patient(patient_id=unique('INT-P'),name='Internal',dob='',sex='')
    m.db.session.add(patient);m.db.session.flush()
    order=m.Order(accession=unique('INT-A'),patient_id=patient.id,modality='DX',procedure='Internal',scheduled=datetime.utcnow())
    policy=m.AssignmentOfferPolicy(name=unique('policy'),enabled=True,mode='ALL')
    m.db.session.add_all([order,policy]);m.db.session.commit()
    candidates=m.assignment_candidate_users(order,policy)
    assert doctor in candidates and other in candidates


def test_external_admin_page_permission_and_direct_url_denial(external_setup):
    m,admin,_,_,tech,*_=external_setup
    client=m.app.test_client()
    assert client.get('/admin/external-intake').status_code==302
    login(client,tech);assert client.get('/admin/external-intake').status_code==403
    login(client,admin);assert client.get('/admin/external-intake').status_code==200


def test_hold_and_reject_never_create_order(external_setup):
    m,admin,_,_,_,_,_,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    client=m.app.test_client();login(client,admin)
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    assert client.post(f'/admin/external-intake/{row.id}/decision',data={'action':'HOLD','note':'check'}).status_code==302
    assert row.status=='HOLD' and row.order_id is None
    assert client.post(f'/admin/external-intake/{row.id}/decision',data={'action':'REJECT','note':'wrong source'}).status_code==302
    assert row.status=='REJECTED' and row.order_id is None


def test_doctor_feed_labels_external_case_separately(external_setup):
    m,_,doctor,_,_,_,center,inbox=external_setup
    patient=m.Patient(patient_id=unique('FEED-P'),name='External feed',dob='',sex='')
    m.db.session.add(patient);m.db.session.flush()
    order=m.Order(accession=unique('FEED-A'),patient_id=patient.id,modality='DX',procedure='External',scheduled=datetime.utcnow(),assigned_doctor_id=doctor.id)
    m.db.session.add(order);m.db.session.flush()
    m.db.session.add(m.ExternalIntakeCase(center_id=center.id,inbox_id=inbox.id,order_id=order.id,status='QUEUED'))
    m.db.session.commit()
    client=m.app.test_client();login(client,doctor)
    payload=client.get('/api/doctor/workspace').get_json()
    item=next(x for x in payload['cases'] if x['id']==order.id)
    assert item['source']=='EXTERNAL' and item['center']==center.name


def test_queue_is_blocked_until_demographics_are_verified(external_setup,monkeypatch):
    m,admin,_,_,_,_,_,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    monkeypatch.setattr(m,'offer_next_doctor',lambda *args,**kwargs:(None,'OFFERED'))
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    client=m.app.test_client();login(client,admin)
    response=client.post(f'/admin/external-intake/{row.id}/decision',data={'action':'QUEUE'})
    assert response.status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.status=='RECEIVED' and row.order_id is None


def test_matched_demographics_allow_queue(external_setup,monkeypatch):
    m,admin,_,_,_,_,_,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    monkeypatch.setattr(m,'offer_next_doctor',lambda *args,**kwargs:(None,'OFFERED'))
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    client=m.app.test_client();login(client,admin)
    response=client.post(f'/admin/external-intake/{row.id}/decision',data={
        'action':'VERIFY','expected_patient_id':'REMOTE-1',
        'expected_patient_name':'External Patient','expected_dob':'19900102',
        'expected_sex':'F','expected_accession':inbox.accession
    })
    assert response.status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.demographic_status=='MATCHED' and row.demographic_score==100
    assert client.post(f'/admin/external-intake/{row.id}/decision',data={'action':'QUEUE'}).status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.status=='QUEUED' and row.order_id is not None


@pytest.mark.parametrize('field,value',[
    ('expected_patient_id','WRONG-ID'),
    ('expected_dob','19881231'),
    ('expected_accession','WRONG-ACCESSION'),
])
def test_critical_demographic_mismatch_blocks_queue(external_setup,field,value):
    m,admin,_,_,_,_,_,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    set_matching_referral(row);setattr(row,field,value)
    result=m.external_intake_demographic_verification(row,persist=True,
                                                      actor_user_id=admin.id)
    m.db.session.commit()
    assert result['status']=='BLOCKED'
    client=m.app.test_client();login(client,admin)
    assert client.post(f'/admin/external-intake/{row.id}/decision',
                       data={'action':'QUEUE'}).status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.status=='RECEIVED' and row.order_id is None


def test_review_required_needs_reasoned_current_facts_approval(external_setup,monkeypatch):
    m,admin,_,_,_,_,_,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    set_matching_referral(row)
    monkeypatch.setattr(m,'external_intake_dicom_demographics',lambda item:({
        'patient_id':'REMOTE-1','patient_name':'External^Patient',
        'dob':'','sex':'F','accession':inbox.accession
    },''))
    result=m.external_intake_demographic_verification(row,persist=True,
                                                      actor_user_id=admin.id)
    m.db.session.commit()
    assert result['status']=='REVIEW_REQUIRED'
    client=m.app.test_client();login(client,admin)
    assert client.post(f'/admin/external-intake/{row.id}/decision',data={
        'action':'APPROVE_REVIEW','note':'Referral document confirms DOB'
    }).status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.demographic_override_approved is True
    assert row.demographic_override_facts_sha256==row.demographic_facts_sha256
    monkeypatch.setattr(m,'offer_next_doctor',lambda *args,**kwargs:(None,'OFFERED'))
    assert client.post(f'/admin/external-intake/{row.id}/decision',
                       data={'action':'QUEUE'}).status_code==302
    assert m.ExternalIntakeCase.query.get(row.id).status=='QUEUED'


def test_review_approval_is_invalidated_when_dicom_facts_change(external_setup,monkeypatch):
    m,admin,_,_,_,_,_,inbox=external_setup
    m.capture_external_pacs_studies();m.db.session.commit()
    row=m.ExternalIntakeCase.query.filter_by(inbox_id=inbox.id).one()
    set_matching_referral(row)
    dicom={'patient_id':'REMOTE-1','patient_name':'External^Patient',
           'dob':'','sex':'F','accession':inbox.accession}
    monkeypatch.setattr(m,'external_intake_dicom_demographics',lambda item:(dict(dicom),''))
    m.external_intake_demographic_verification(row,persist=True,actor_user_id=admin.id)
    m.db.session.commit()
    client=m.app.test_client();login(client,admin)
    assert client.post(f'/admin/external-intake/{row.id}/decision',data={
        'action':'APPROVE_REVIEW','note':'Referral confirms missing DICOM DOB'
    }).status_code==302
    dicom['patient_name']='Different^Name'
    assert client.post(f'/admin/external-intake/{row.id}/decision',
                       data={'action':'QUEUE'}).status_code==302
    m.db.session.expire_all();row=m.ExternalIntakeCase.query.get(row.id)
    assert row.status=='RECEIVED' and row.order_id is None

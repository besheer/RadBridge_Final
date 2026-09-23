from werkzeug.security import generate_password_hash


def login(client,user):
    with client.session_transaction() as session:
        session['uid']=user.id


def make_user(m,username,role_code,branch=None,perms=()):
    role=m.Role.query.filter_by(code=role_code).first()
    if role is None:
        role=m.Role(code=role_code,name=role_code.replace('_',' ').title(),permissions_json='[]')
        m.db.session.add(role);m.db.session.flush()
    role.permissions_json=m.json.dumps(list(perms))
    user=m.User(username=username,full_name=username,password_hash=generate_password_hash('secret'),role_id=role.id,branch_id=(branch.id if branch else None),active=True)
    m.db.session.add(user);m.db.session.commit()
    return user


def make_case(m,suffix,branch,phone='01000000000'):
    patient=m.Patient(patient_id=f'CR-P-{suffix}',name=f'Correction Patient {suffix}',phone=phone)
    m.db.session.add(patient);m.db.session.flush()
    order=m.Order(patient_id=patient.id,accession=f'CR-ACC-{suffix}',modality='CT',procedure='CT Brain',scheduled=m.datetime.utcnow(),status='REGISTERED',exam_status='ORDERED',branch_id=branch.id,pacs_image_count=1,pacs_status='IMAGES_COMPLETE',pacs_study_id=f'study-{suffix}')
    m.db.session.add(order);m.db.session.commit()
    return patient,order


def test_correction_permissions_are_declared(app_ctx):
    m=app_ctx
    for perm in ('correction.request','correction.review','correction.execute'):
        assert perm in m.ALL_PERMISSIONS
    assert 'correction.request' in m.ROLE_PERMS['RECEPTION']
    assert 'correction.request' in m.ROLE_PERMS['TECHNICIAN']
    assert 'correction.request' in m.ROLE_PERMS['BRANCH_MANAGER']
    assert 'correction.review' in m.ROLE_PERMS['CASE_COORDINATOR']


def test_search_supports_phone_and_order_id_with_branch_scope(app_ctx):
    m=app_ctx
    b1=m.Branch(code='CR-B1',name='Correction Branch 1');b2=m.Branch(code='CR-B2',name='Correction Branch 2')
    m.db.session.add_all([b1,b2]);m.db.session.commit()
    _,o1=make_case(m,'ONE',b1,'01011112222');_,o2=make_case(m,'TWO',b2,'01011112222')
    user=make_user(m,'cr-tech-search','TECHNICIAN',b1,('correction.request',))
    with m.app.test_request_context('/'):
        m.session['uid']=user.id
        rows=m.correction_search_orders('01011112222',user)
        assert [x.id for x in rows]==[o1.id]
        rows=m.correction_search_orders(str(o1.id),user)
        assert o1 in rows
        assert o2 not in rows


def test_request_submission_is_audited_and_non_destructive(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B3',name='Correction Branch 3');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'REQ',branch)
    user=make_user(m,'cr-tech-submit','TECHNICIAN',branch,('correction.request',))
    client=m.app.test_client();login(client,user)
    before=(order.status,order.exam_status,order.pacs_image_count,order.pacs_status,order.pacs_study_id)
    response=client.post('/correction-center/request',data={'order_id':order.id,'request_type':'WRONG_IMAGES','reason':'Images belong to another case'})
    assert response.status_code==302
    row=m.CorrectionRequest.query.filter_by(order_id=order.id,request_type='WRONG_IMAGES').first()
    assert row and row.status=='NEW' and row.requested_by==user.id
    m.db.session.refresh(order)
    after=(order.status,order.exam_status,order.pacs_image_count,order.pacs_status,order.pacs_study_id)
    assert after==before
    audit=m.AuditLog.query.filter_by(action='CORRECTION_REQUEST_CREATED',entity_id=str(row.id)).first()
    assert audit is not None


def test_duplicate_open_request_is_blocked(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B4',name='Correction Branch 4');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'DUP',branch)
    user=make_user(m,'cr-tech-dup','TECHNICIAN',branch,('correction.request',))
    client=m.app.test_client();login(client,user)
    data={'order_id':order.id,'request_type':'WRONG_IMAGES','reason':'Wrong images need coordinator review'}
    assert client.post('/correction-center/request',data=data).status_code==302
    assert client.post('/correction-center/request',data=data).status_code==409
    assert m.CorrectionRequest.query.filter_by(order_id=order.id,request_type='WRONG_IMAGES').count()==1


def test_cross_branch_request_is_forbidden(app_ctx):
    m=app_ctx
    b1=m.Branch(code='CR-B5',name='Correction Branch 5');b2=m.Branch(code='CR-B6',name='Correction Branch 6')
    m.db.session.add_all([b1,b2]);m.db.session.commit()
    _,order=make_case(m,'CROSS',b2)
    user=make_user(m,'cr-tech-cross','TECHNICIAN',b1,('correction.request',))
    client=m.app.test_client();login(client,user)
    r=client.post('/correction-center/request',data={'order_id':order.id,'request_type':'CANCEL_ORDER','reason':'Wrong order was created'})
    assert r.status_code==403
    assert m.CorrectionRequest.query.filter_by(order_id=order.id).count()==0


def test_requester_cannot_approve_own_request(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B7',name='Correction Branch 7');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'SELF',branch)
    user=make_user(m,'cr-coord-self','CASE_COORDINATOR',branch,('correction.request','correction.review'))
    row=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='NEW',reason='Wrong images',requested_by=user.id)
    m.db.session.add(row);m.db.session.commit()
    client=m.app.test_client();login(client,user)
    r=client.post(f'/correction-center/requests/{row.id}/action',data={'action':'APPROVE','note':'Reviewed and approve correction'})
    assert r.status_code==409
    m.db.session.refresh(row);assert row.status=='NEW'


def test_coordinator_can_approve_without_mutating_case(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B8',name='Correction Branch 8');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'APPROVE',branch)
    requester=make_user(m,'cr-tech-approve','TECHNICIAN',branch,('correction.request',))
    reviewer=make_user(m,'cr-coord-approve','CASE_COORDINATOR',branch,('correction.review',))
    row=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='NEW',reason='Wrong images',requested_by=requester.id)
    m.db.session.add(row);m.db.session.commit()
    before=(order.status,order.exam_status,order.pacs_image_count,order.pacs_status,order.pacs_study_id)
    client=m.app.test_client();login(client,reviewer)
    r=client.post(f'/correction-center/requests/{row.id}/action',data={'action':'APPROVE','note':'Validated request; action still requires protected workflow'})
    assert r.status_code==302
    m.db.session.refresh(row);m.db.session.refresh(order)
    assert row.status=='APPROVED' and row.assigned_to==reviewer.id
    assert (order.status,order.exam_status,order.pacs_image_count,order.pacs_status,order.pacs_study_id)==before
    assert m.AuditLog.query.filter_by(action='CORRECTION_REQUEST_REVIEW',entity_id=str(row.id)).first() is not None


def test_non_reviewer_cannot_open_coordinator_queue(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B9',name='Correction Branch 9');m.db.session.add(branch);m.db.session.commit()
    user=make_user(m,'cr-tech-no-review','TECHNICIAN',branch,('correction.request',))
    client=m.app.test_client();login(client,user)
    assert client.get('/correction-center/requests').status_code==403



def test_request_only_user_without_branch_fails_closed(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B10',name='Correction Branch 10');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'NOBRANCH',branch)
    user=make_user(m,'cr-tech-no-branch','TECHNICIAN',None,('correction.request',))
    client=m.app.test_client();login(client,user)
    assert client.get('/correction-center?q=CR-ACC-NOBRANCH').status_code==200
    with m.app.test_request_context('/'):
        m.session['uid']=user.id
        assert m.correction_search_orders('CR-ACC-NOBRANCH',user)==[]
    r=client.post('/correction-center/request',data={'order_id':order.id,'request_type':'WRONG_IMAGES','reason':'Wrong images need review'})
    assert r.status_code==403


def test_approved_request_cannot_be_marked_complete_manually(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B11',name='Correction Branch 11');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'NOCOMPLETE',branch)
    requester=make_user(m,'cr-tech-no-complete','TECHNICIAN',branch,('correction.request',))
    reviewer=make_user(m,'cr-coord-no-complete','CASE_COORDINATOR',branch,('correction.review',))
    row=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='APPROVED',reason='Wrong images',requested_by=requester.id,assigned_to=reviewer.id)
    m.db.session.add(row);m.db.session.commit()
    client=m.app.test_client();login(client,reviewer)
    r=client.post(f'/correction-center/requests/{row.id}/action',data={'action':'COMPLETE','note':'Trying to bypass execution workflow'})
    assert r.status_code==400
    m.db.session.refresh(row);assert row.status=='APPROVED'

def test_dashboard_contains_correction_entry():
    from pathlib import Path
    text=Path('templates/dashboard.html').read_text()
    assert "url_for('correction_center')" in text
    assert 'Correction & Cancellation' in text


def test_requester_cannot_claim_or_need_info_on_own_request(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B12',name='Correction Branch 12');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'SELFREVIEW',branch)
    user=make_user(m,'cr-coord-self-review','CASE_COORDINATOR',branch,('correction.request','correction.review'))
    row=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='NEW',reason='Wrong images',requested_by=user.id)
    m.db.session.add(row);m.db.session.commit()
    client=m.app.test_client();login(client,user)
    for action,data in (
        ('CLAIM',{'action':'CLAIM'}),
        ('NEED_INFO',{'action':'NEED_INFO','note':'Need more information'}),
    ):
        r=client.post(f'/correction-center/requests/{row.id}/action',data=data)
        assert r.status_code==409
        m.db.session.refresh(row)
        assert row.status=='NEW' and row.assigned_to is None


def test_approved_request_cannot_be_rejected_or_need_info(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B13',name='Correction Branch 13');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'LOCKEDAPPROVAL',branch)
    requester=make_user(m,'cr-tech-locked-approval','TECHNICIAN',branch,('correction.request',))
    reviewer=make_user(m,'cr-coord-locked-approval','CASE_COORDINATOR',branch,('correction.review',))
    row=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='APPROVED',reason='Wrong images',requested_by=requester.id,assigned_to=reviewer.id)
    m.db.session.add(row);m.db.session.commit()
    client=m.app.test_client();login(client,reviewer)
    for action in ('REJECT','NEED_INFO'):
        r=client.post(f'/correction-center/requests/{row.id}/action',data={'action':action,'note':'Attempt invalid state transition'})
        assert r.status_code==409
        m.db.session.refresh(row)
        assert row.status=='APPROVED'


def test_database_blocks_duplicate_open_requests(app_ctx):
    from sqlalchemy.exc import IntegrityError
    m=app_ctx
    branch=m.Branch(code='CR-B14',name='Correction Branch 14');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'DBDUP',branch)
    requester=make_user(m,'cr-tech-dbdup','TECHNICIAN',branch,('correction.request',))
    first=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='NEW',reason='First request',requested_by=requester.id)
    m.db.session.add(first);m.db.session.commit()
    second=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='UNDER_REVIEW',reason='Concurrent duplicate',requested_by=requester.id)
    m.db.session.add(second)
    try:
        m.db.session.commit()
        raised=False
    except IntegrityError:
        m.db.session.rollback()
        raised=True
    assert raised is True
    assert m.CorrectionRequest.query.filter_by(order_id=order.id,request_type='WRONG_IMAGES').count()==1


def test_closed_request_allows_new_request_of_same_type(app_ctx):
    m=app_ctx
    branch=m.Branch(code='CR-B15',name='Correction Branch 15');m.db.session.add(branch);m.db.session.commit()
    _,order=make_case(m,'REOPEN',branch)
    requester=make_user(m,'cr-tech-reopen','TECHNICIAN',branch,('correction.request',))
    old=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='REJECTED',reason='Old rejected request',requested_by=requester.id)
    m.db.session.add(old);m.db.session.commit()
    new=m.CorrectionRequest(order_id=order.id,branch_id=branch.id,request_type='WRONG_IMAGES',status='NEW',reason='New request after closure',requested_by=requester.id)
    m.db.session.add(new);m.db.session.commit()
    assert m.CorrectionRequest.query.filter_by(order_id=order.id,request_type='WRONG_IMAGES').count()==2

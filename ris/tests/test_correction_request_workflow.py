from web.source_contract import get_source as _get_source
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


# RB_CORRECTION_PHASE2A_EXECUTION_TESTS_V1

def _make_phase2a_approved_request(
    m,
    suffix,
    branch,
    requester,
    reviewer,
):
    _,order=make_case(
        m,
        suffix,
        branch
    )

    row=m.CorrectionRequest(
        order_id=order.id,
        branch_id=branch.id,
        request_type='WRONG_IMAGES',
        status='APPROVED',
        reason='Phase 2A execution ledger test',
        requested_by=requester.id,
        assigned_to=reviewer.id,
        review_note='Approved for Phase 2A test only',
    )

    m.db.session.add(row)
    m.db.session.commit()

    return order,row


def test_phase2a_execution_model_declared(
    app_ctx
):
    m=app_ctx

    assert (
        m.CorrectionExecution.__tablename__
        ==
        'correction_execution'
    )

    cols={
        c.name
        for c in
        m.CorrectionExecution.__table__.columns
    }

    required={
        'id',
        'correction_request_id',
        'order_id',
        'branch_id',
        'execution_type',
        'status',
        'state_version',
        'claimed_by',
        'executed_by',
        'request_snapshot_json',
        'preflight_snapshot_json',
        'result_snapshot_json',
        'confirmation_token_hash',
        'confirmation_expires_at',
        'failure_code',
        'failure_message',
        'created_at',
        'updated_at',
        'claimed_at',
        'started_at',
        'executed_at',
        'verified_at',
        'failed_at',
    }

    assert required == cols


def test_phase2a_prepare_requires_approved_request(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B1',
        name='Phase2A Branch 1'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-1',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    _,order=make_case(
        m,
        'P2A-NOTAPPROVED',
        branch
    )

    row=m.CorrectionRequest(
        order_id=order.id,
        branch_id=branch.id,
        request_type='WRONG_IMAGES',
        status='NEW',
        reason='Not approved',
        requested_by=requester.id,
    )

    m.db.session.add(row)
    m.db.session.commit()

    import pytest

    with pytest.raises(
        ValueError,
        match='CORRECTION_REQUEST_NOT_APPROVED'
    ):
        m.correction_execution_prepare(row)


def test_phase2a_prepare_is_non_destructive(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B2',
        name='Phase2A Branch 2'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-2',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    reviewer=make_user(
        m,
        'p2a-reviewer-2',
        'CASE_COORDINATOR',
        branch,
        ('correction.review',)
    )

    order,row=_make_phase2a_approved_request(
        m,
        'P2A-PREP',
        branch,
        requester,
        reviewer
    )

    before=(
        order.status,
        order.exam_status,
        order.pacs_status,
        order.pacs_image_count,
        order.pacs_study_id,
        order.study_instance_uid,
        row.status,
        row.requested_by,
        row.assigned_to,
    )

    execution=m.correction_execution_prepare(
        row
    )

    m.db.session.commit()
    m.db.session.refresh(order)
    m.db.session.refresh(row)
    m.db.session.refresh(execution)

    after=(
        order.status,
        order.exam_status,
        order.pacs_status,
        order.pacs_image_count,
        order.pacs_study_id,
        order.study_instance_uid,
        row.status,
        row.requested_by,
        row.assigned_to,
    )

    assert before == after

    assert (
        execution.status
        ==
        'READY_FOR_EXECUTION'
    )

    assert execution.state_version == 1
    assert execution.order_id == order.id

    assert (
        execution.correction_request_id
        ==
        row.id
    )


def test_phase2a_one_execution_per_request(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B3',
        name='Phase2A Branch 3'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-3',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    reviewer=make_user(
        m,
        'p2a-reviewer-3',
        'CASE_COORDINATOR',
        branch,
        ('correction.review',)
    )

    _,row=_make_phase2a_approved_request(
        m,
        'P2A-UNIQUE',
        branch,
        requester,
        reviewer
    )

    m.correction_execution_prepare(row)
    m.db.session.commit()

    import pytest

    with pytest.raises(
        ValueError,
        match='CORRECTION_EXECUTION_ALREADY_EXISTS'
    ):
        m.correction_execution_prepare(row)


def test_phase2a_requester_cannot_execute(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B4',
        name='Phase2A Branch 4'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-4',
        'TECHNICIAN',
        branch,
        (
            'correction.request',
            'correction.execute',
        )
    )

    reviewer=make_user(
        m,
        'p2a-reviewer-4',
        'CASE_COORDINATOR',
        branch,
        ('correction.review',)
    )

    _,row=_make_phase2a_approved_request(
        m,
        'P2A-REQUESTER',
        branch,
        requester,
        reviewer
    )

    execution=m.correction_execution_prepare(
        row
    )

    m.db.session.commit()

    import pytest

    with pytest.raises(
        PermissionError,
        match='REQUESTER_CANNOT_EXECUTE'
    ):
        m.correction_execution_transition(
            execution,
            'CLAIMED_FOR_EXECUTION',
            requester
        )


def test_phase2a_reviewer_cannot_execute(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B5',
        name='Phase2A Branch 5'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-5',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    reviewer=make_user(
        m,
        'p2a-reviewer-5',
        'CASE_COORDINATOR',
        branch,
        (
            'correction.review',
            'correction.execute',
        )
    )

    _,row=_make_phase2a_approved_request(
        m,
        'P2A-REVIEWER',
        branch,
        requester,
        reviewer
    )

    execution=m.correction_execution_prepare(
        row
    )

    m.db.session.commit()

    import pytest

    with pytest.raises(
        PermissionError,
        match='REVIEWER_CANNOT_EXECUTE'
    ):
        m.correction_execution_transition(
            execution,
            'CLAIMED_FOR_EXECUTION',
            reviewer
        )


def test_phase2a_executor_requires_permission(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B6',
        name='Phase2A Branch 6'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-6',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    reviewer=make_user(
        m,
        'p2a-reviewer-6',
        'CASE_COORDINATOR',
        branch,
        ('correction.review',)
    )

    executor=make_user(
        m,
        'p2a-executor-no-perm',
        'TECHNICIAN',
        branch,
        ()
    )

    _,row=_make_phase2a_approved_request(
        m,
        'P2A-NOPERM',
        branch,
        requester,
        reviewer
    )

    execution=m.correction_execution_prepare(
        row
    )

    m.db.session.commit()

    import pytest

    with pytest.raises(
        PermissionError,
        match='CORRECTION_EXECUTE_PERMISSION_REQUIRED'
    ):
        m.correction_execution_transition(
            execution,
            'CLAIMED_FOR_EXECUTION',
            executor
        )


def test_phase2a_claim_hold_release_versioning(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B7',
        name='Phase2A Branch 7'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-7',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    reviewer=make_user(
        m,
        'p2a-reviewer-7',
        'CASE_COORDINATOR',
        branch,
        ('correction.review',)
    )

    executor=make_user(
        m,
        'p2a-executor-7',
        'TECHNICIAN',
        branch,
        ('correction.execute',)
    )

    _,row=_make_phase2a_approved_request(
        m,
        'P2A-VERSION',
        branch,
        requester,
        reviewer
    )

    execution=m.correction_execution_prepare(
        row
    )

    assert execution.state_version == 1

    m.correction_execution_transition(
        execution,
        'CLAIMED_FOR_EXECUTION',
        executor
    )

    assert (
        execution.status
        ==
        'CLAIMED_FOR_EXECUTION'
    )
    assert execution.state_version == 2
    assert execution.claimed_by == executor.id
    assert execution.claimed_at is not None

    m.correction_execution_hold(
        execution,
        executor
    )

    assert execution.status == 'ON_HOLD'
    assert execution.state_version == 3

    m.correction_execution_release(
        execution,
        executor
    )

    assert (
        execution.status
        ==
        'READY_FOR_EXECUTION'
    )
    assert execution.state_version == 4
    assert execution.claimed_by is None


def test_phase2a_invalid_transition_fails_closed(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2A-B8',
        name='Phase2A Branch 8'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2a-requester-8',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    reviewer=make_user(
        m,
        'p2a-reviewer-8',
        'CASE_COORDINATOR',
        branch,
        ('correction.review',)
    )

    executor=make_user(
        m,
        'p2a-executor-8',
        'TECHNICIAN',
        branch,
        ('correction.execute',)
    )

    _,row=_make_phase2a_approved_request(
        m,
        'P2A-INVALID',
        branch,
        requester,
        reviewer
    )

    execution=m.correction_execution_prepare(
        row
    )

    import pytest

    with pytest.raises(
        ValueError,
        match='INVALID_CORRECTION_EXECUTION_TRANSITION'
    ):
        m.correction_execution_transition(
            execution,
            'COMPLETED',
            executor
        )

    assert (
        execution.status
        ==
        'READY_FOR_EXECUTION'
    )

    assert execution.state_version == 1


def test_phase2a_no_destructive_execution_route_added(
    app_ctx
):
    import inspect

    m=app_ctx

    source=_get_source(m)

    assert (
        '@app.post("/correction-center/execute'
        not in source
    )

    assert (
        "@app.post('/correction-center/execute"
        not in source
    )

    assert (
        'CORRECTION_EXECUTION_DELETE'
        not in source
    )

    assert (
        'CORRECTION_EXECUTION_REMAP'
        not in source
    )



# RB_CORRECTION_PHASE2A_HARDENING_TESTS_V1

def _phase2a_hardening_fixture(
    m,
    suffix,
):
    branch=m.Branch(
        code='P2AH-'+suffix,
        name='Phase2A Hardening '+suffix
    )

    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        'p2ah-requester-'+suffix,
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    reviewer=make_user(
        m,
        'p2ah-reviewer-'+suffix,
        'CASE_COORDINATOR',
        branch,
        ('correction.review',)
    )

    executor=make_user(
        m,
        'p2ah-executor-'+suffix,
        'TECHNICIAN',
        branch,
        ('correction.execute',)
    )

    executor2=make_user(
        m,
        'p2ah-executor2-'+suffix,
        'TECHNICIAN',
        branch,
        ('correction.execute',)
    )

    order,row=_make_phase2a_approved_request(
        m,
        'P2AH-'+suffix,
        branch,
        requester,
        reviewer,
    )

    execution=m.correction_execution_prepare(
        row
    )

    m.db.session.commit()

    return (
        branch,
        requester,
        reviewer,
        executor,
        executor2,
        order,
        row,
        execution,
    )


def test_phase2a_prepare_and_transition_use_row_locks(
    app_ctx
):
    import inspect

    m=app_ctx

    prepare_source=_get_source(
        m.correction_execution_prepare
    )

    transition_source=_get_source(
        m.correction_execution_transition
    )

    request_lock_source=_get_source(
        m.correction_execution_request_lock
    )

    execution_lock_source=_get_source(
        m.correction_execution_row_lock
    )

    assert (
        'correction_execution_request_lock'
        in prepare_source
    )

    assert (
        'correction_execution_row_lock'
        in transition_source
    )

    assert (
        '.with_for_update()'
        in request_lock_source
    )

    assert (
        '.with_for_update()'
        in execution_lock_source
    )


def test_phase2a_stale_state_version_fails_closed(
    app_ctx
):
    import pytest

    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        _,
        _,
        execution,
    )=_phase2a_hardening_fixture(
        m,
        'VERSION'
    )

    m.correction_execution_transition(
        execution,
        'CLAIMED_FOR_EXECUTION',
        executor,
        expected_version=1,
    )

    assert execution.state_version==2

    with pytest.raises(
        ValueError,
        match='CORRECTION_EXECUTION_STALE_VERSION'
    ):
        m.correction_execution_hold(
            execution,
            executor,
            expected_version=1,
        )

    m.db.session.refresh(execution)

    assert (
        execution.status
        ==
        'CLAIMED_FOR_EXECUTION'
    )

    assert execution.state_version==2


def test_phase2a_changed_clinical_snapshot_blocks_transition(
    app_ctx
):
    import pytest

    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        order,
        _,
        execution,
    )=_phase2a_hardening_fixture(
        m,
        'SNAPSHOT'
    )

    original=order.pacs_status

    order.pacs_status=(
        'WAITING'
        if original!='WAITING'
        else 'IMAGES_COMPLETE'
    )

    m.db.session.commit()

    with pytest.raises(
        ValueError,
        match='CORRECTION_EXECUTION_STALE_SNAPSHOT'
    ):
        m.correction_execution_transition(
            execution,
            'CLAIMED_FOR_EXECUTION',
            executor,
            expected_version=1,
        )

    m.db.session.refresh(execution)

    assert (
        execution.status
        ==
        'READY_FOR_EXECUTION'
    )

    assert execution.state_version==1


def test_phase2a_request_losing_approval_blocks_execution(
    app_ctx
):
    import pytest

    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        _,
        row,
        execution,
    )=_phase2a_hardening_fixture(
        m,
        'APPROVAL'
    )

    row.status='REJECTED'
    m.db.session.commit()

    with pytest.raises(
        ValueError,
        match='CORRECTION_REQUEST_NO_LONGER_APPROVED'
    ):
        m.correction_execution_transition(
            execution,
            'CLAIMED_FOR_EXECUTION',
            executor,
            expected_version=1,
        )

    m.db.session.refresh(execution)

    assert (
        execution.status
        ==
        'READY_FOR_EXECUTION'
    )

    assert execution.state_version==1


def test_phase2a_second_executor_cannot_control_claim(
    app_ctx
):
    import pytest

    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        executor2,
        _,
        _,
        execution,
    )=_phase2a_hardening_fixture(
        m,
        'CLAIM'
    )

    m.correction_execution_transition(
        execution,
        'CLAIMED_FOR_EXECUTION',
        executor,
        expected_version=1,
    )

    assert execution.claimed_by==executor.id
    assert execution.state_version==2

    with pytest.raises(
        PermissionError,
        match='CORRECTION_EXECUTION_CLAIMED_BY_ANOTHER_USER'
    ):
        m.correction_execution_hold(
            execution,
            executor2,
            expected_version=2,
        )

    m.db.session.refresh(execution)

    assert execution.claimed_by==executor.id

    assert (
        execution.status
        ==
        'CLAIMED_FOR_EXECUTION'
    )

    assert execution.state_version==2



# RB_CORRECTION_PHASE2A_PREVIEW_ROUTE_TESTS_V1

def test_phase2a_execution_queue_requires_execute_permission(
    app_ctx
):
    m=app_ctx

    branch=m.Branch(
        code='P2AR-B1',
        name='Phase2A Route Branch 1'
    )

    m.db.session.add(branch)
    m.db.session.commit()

    user=make_user(
        m,
        'p2ar-noexec',
        'TECHNICIAN',
        branch,
        ('correction.request',)
    )

    client=m.app.test_client()
    login(client,user)

    r=client.get(
        '/correction-center/executions'
    )

    assert r.status_code==403


def test_phase2a_prepare_route_is_non_destructive(
    app_ctx
):
    m=app_ctx

    (
        branch,
        requester,
        reviewer,
        executor,
        _,
        order,
        row,
        _
    )=_phase2a_hardening_fixture(
        m,
        'ROUTEPREP'
    )

    # Remove fixture-created ledger so route can prepare it.
    m.CorrectionExecution.query.delete()
    m.db.session.commit()

    before=(
        order.status,
        order.exam_status,
        order.pacs_status,
        order.pacs_image_count,
        order.pacs_study_id,
        order.study_instance_uid,
        row.status,
    )

    client=m.app.test_client()
    login(client,executor)

    r=client.post(
        f'/correction-center/requests/{row.id}/execution/prepare',
        follow_redirects=False
    )

    assert r.status_code in (302,303)

    execution=(
        m.CorrectionExecution.query
        .filter_by(
            correction_request_id=row.id
        )
        .one()
    )

    m.db.session.refresh(order)
    m.db.session.refresh(row)

    after=(
        order.status,
        order.exam_status,
        order.pacs_status,
        order.pacs_image_count,
        order.pacs_study_id,
        order.study_instance_uid,
        row.status,
    )

    assert before==after
    assert execution.status=='READY_FOR_EXECUTION'
    assert execution.state_version==1


def test_phase2a_requester_cannot_prepare_ledger_route(
    app_ctx
):
    m=app_ctx

    (
        _,
        requester,
        _,
        _,
        _,
        _,
        row,
        _
    )=_phase2a_hardening_fixture(
        m,
        'ROUTEREQ'
    )

    m.CorrectionExecution.query.delete()

    requester.role.permissions_json=(
        '["correction.request","correction.execute"]'
    )

    m.db.session.commit()

    client=m.app.test_client()
    login(client,requester)

    r=client.post(
        f'/correction-center/requests/{row.id}/execution/prepare'
    )

    assert r.status_code==403

    assert (
        m.CorrectionExecution.query.count()
        ==
        0
    )


def test_phase2a_reviewer_cannot_prepare_ledger_route(
    app_ctx
):
    m=app_ctx

    (
        _,
        _,
        reviewer,
        _,
        _,
        _,
        row,
        _
    )=_phase2a_hardening_fixture(
        m,
        'ROUTEREV'
    )

    m.CorrectionExecution.query.delete()

    reviewer.role.permissions_json=(
        '["correction.review","correction.execute"]'
    )

    m.db.session.commit()

    client=m.app.test_client()
    login(client,reviewer)

    r=client.post(
        f'/correction-center/requests/{row.id}/execution/prepare'
    )

    assert r.status_code==403

    assert (
        m.CorrectionExecution.query.count()
        ==
        0
    )


def test_phase2a_claim_hold_release_routes(
    app_ctx
):
    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        _,
        _,
        execution
    )=_phase2a_hardening_fixture(
        m,
        'ROUTEFLOW'
    )

    client=m.app.test_client()
    login(client,executor)

    r=client.post(
        f'/correction-center/executions/{execution.id}/claim',
        data={
            'expected_version':'1'
        },
        follow_redirects=False
    )

    assert r.status_code in (302,303)

    m.db.session.refresh(execution)

    assert (
        execution.status
        ==
        'CLAIMED_FOR_EXECUTION'
    )

    assert execution.state_version==2

    r=client.post(
        f'/correction-center/executions/{execution.id}/hold',
        data={
            'expected_version':'2'
        },
        follow_redirects=False
    )

    assert r.status_code in (302,303)

    m.db.session.refresh(execution)

    assert execution.status=='ON_HOLD'
    assert execution.state_version==3

    r=client.post(
        f'/correction-center/executions/{execution.id}/release',
        data={
            'expected_version':'3'
        },
        follow_redirects=False
    )

    assert r.status_code in (302,303)

    m.db.session.refresh(execution)

    assert (
        execution.status
        ==
        'READY_FOR_EXECUTION'
    )

    assert execution.state_version==4


def test_phase2a_stale_version_route_returns_409(
    app_ctx
):
    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        _,
        _,
        execution
    )=_phase2a_hardening_fixture(
        m,
        'ROUTESTALE'
    )

    client=m.app.test_client()
    login(client,executor)

    r=client.post(
        f'/correction-center/executions/{execution.id}/claim',
        data={
            'expected_version':'99'
        }
    )

    assert r.status_code==409

    m.db.session.refresh(execution)

    assert (
        execution.status
        ==
        'READY_FOR_EXECUTION'
    )

    assert execution.state_version==1


def test_phase2a_execution_template_has_no_destructive_action(
    app_ctx
):
    from pathlib import Path

    m=app_ctx

    path=Path(
        m.app.root_path
    ) / 'templates' / 'correction_execution_queue.html'

    text=path.read_text(
        encoding='utf-8'
    )

    assert 'Prepare Execution Ledger' in text
    assert '>Claim<' not in text or 'Claim' in text
    assert 'Hold' in text
    assert 'Release' in text

    forbidden=(
        'Delete Images',
        'Delete PACS',
        'Execute Delete',
        'Execute Cancellation',
        'Merge Patient',
        'Execute Merge',
        'Remap Study',
        'Execute Remap',
    )

    for item in forbidden:
        assert item not in text


def _phase2b_execution_fixture(m,suffix):
    branch=m.Branch(
        code=f'P2B-{suffix}',
        name=f'Phase2B {suffix}',
    )
    m.db.session.add(branch)
    m.db.session.commit()

    requester=make_user(
        m,
        f'p2b-requester-{suffix}',
        'TECHNICIAN',
        branch,
        ('correction.request',),
    )

    reviewer=make_user(
        m,
        f'p2b-reviewer-{suffix}',
        'CASE_COORDINATOR',
        branch,
        ('correction.review',),
    )

    executor=make_user(
        m,
        f'p2b-executor-{suffix}',
        'SUPER_ADMIN',
        branch,
        (),
    )

    patient,order=make_case(
        m,
        f'P2B-{suffix}',
        branch,
    )

    order.pacs_status='IMAGES_COMPLETE'
    order.pacs_image_count=7
    order.pacs_study_id=f'study-p2b-{suffix}'
    order.study_instance_uid=f'1.2.840.p2b.{suffix}'

    request_row=m.CorrectionRequest(
        order_id=order.id,
        branch_id=branch.id,
        request_type='WRONG_IMAGES',
        status='APPROVED',
        reason='Approved wrong images request',
        requested_by=requester.id,
        assigned_to=reviewer.id,
    )

    m.db.session.add(request_row)
    m.db.session.flush()

    snapshot=m.correction_execution_snapshot(
        request_row
    )

    execution=m.CorrectionExecution(
        correction_request_id=request_row.id,
        order_id=order.id,
        branch_id=branch.id,
        execution_type='WRONG_IMAGES',
        status='CLAIMED_FOR_EXECUTION',
        state_version=4,
        claimed_by=executor.id,
        request_snapshot_json=m.json.dumps(
            snapshot,
            sort_keys=True,
            separators=(',',':'),
            default=str,
        ),
        preflight_snapshot_json='',
        result_snapshot_json='',
    )

    m.db.session.add(execution)
    m.db.session.commit()

    return (
        branch,
        requester,
        reviewer,
        executor,
        patient,
        order,
        request_row,
        execution,
    )


def _phase2b_allowed_preflight(order):
    return {
        'allowed':True,
        'blockers':[],
        'reason':'Approved execution reason',
        'typed_accession':order.accession,
        'accession':order.accession,
        'study_id':order.pacs_study_id,
        'orthanc_status':200,
        'orthanc_error':'',
        'same_study_order_count':1,
        'active_transfer_count':0,
    }


def test_phase2b_wrong_images_success_uses_shared_primitive(
    monkeypatch,
    app_ctx,
):
    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        order,
        request_row,
        execution,
    )=_phase2b_execution_fixture(
        m,
        'SUCCESS',
    )

    calls={'count':0}

    def fake_shared(
        order_arg,
        accession_arg,
        reason_arg,
        preflight=None,
        after_delete=None,
    ):
        calls['count']+=1

        assert order_arg.id==order.id
        assert accession_arg==order.accession
        assert reason_arg=='Approved execution reason'

        assert preflight is not None
        assert preflight['allowed'] is True
        assert after_delete is not None
        after_delete()

        order_arg.pacs_status='IMAGES_DELETED'
        order_arg.pacs_image_count=0

        return {
            'ok':True,
            'deleted':True,
            'ris_state_updated':True,
            'order_id':order_arg.id,
        },200

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_preflight',
        lambda order_arg,*a,**k: _phase2b_allowed_preflight(order_arg),
    )

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_execute',
        fake_shared,
    )

    with m.app.test_request_context(
        '/correction-center/executions/test/execute',
        method='POST',
    ):
        m.session['uid']=executor.id

        payload,status=m.correction_wrong_images_execute(
            execution.id,
            executor,
            4,
            order.accession,
            'Approved execution reason',
        )

    assert status==200
    assert payload['ok'] is True
    assert calls['count']==1

    m.db.session.refresh(execution)
    m.db.session.refresh(request_row)

    assert execution.status=='COMPLETED'
    assert execution.state_version==8
    assert execution.executed_by==executor.id
    assert request_row.status=='COMPLETED'


def test_phase2b_stale_version_blocks_before_shared_primitive(
    monkeypatch,
    app_ctx,
):
    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        order,
        _,
        execution,
    )=_phase2b_execution_fixture(
        m,
        'STALEVER',
    )

    calls={'count':0}

    def fail_shared(*args,**kwargs):
        calls['count']+=1
        raise AssertionError(
            'shared primitive must not run'
        )

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_execute',
        fail_shared,
    )

    payload,status=m.correction_wrong_images_execute(
        execution.id,
        executor,
        99,
        order.accession,
        'Approved execution reason',
    )

    assert status==409
    assert payload['error']=='STALE_VERSION'
    assert calls['count']==0

    m.db.session.refresh(execution)

    assert execution.status=='CLAIMED_FOR_EXECUTION'
    assert execution.state_version==4


def test_phase2b_requester_cannot_execute(
    monkeypatch,
    app_ctx,
):
    m=app_ctx

    (
        _,
        requester,
        _,
        _,
        _,
        order,
        _,
        execution,
    )=_phase2b_execution_fixture(
        m,
        'REQUESTER',
    )

    execution.claimed_by=requester.id
    m.db.session.commit()

    calls={'count':0}

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_execute',
        lambda *a,**k: (
            calls.__setitem__(
                'count',
                calls['count']+1
            )
        ),
    )

    payload,status=m.correction_wrong_images_execute(
        execution.id,
        requester,
        4,
        order.accession,
        'Approved execution reason',
    )

    assert status==409
    assert payload['error']=='REQUESTER_CANNOT_EXECUTE'
    assert calls['count']==0


def test_phase2b_reviewer_cannot_execute(
    monkeypatch,
    app_ctx,
):
    m=app_ctx

    (
        _,
        _,
        reviewer,
        _,
        _,
        order,
        _,
        execution,
    )=_phase2b_execution_fixture(
        m,
        'REVIEWER',
    )

    execution.claimed_by=reviewer.id
    m.db.session.commit()

    calls={'count':0}

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_execute',
        lambda *a,**k: (
            calls.__setitem__(
                'count',
                calls['count']+1
            )
        ),
    )

    payload,status=m.correction_wrong_images_execute(
        execution.id,
        reviewer,
        4,
        order.accession,
        'Approved execution reason',
    )

    assert status==409
    assert payload['error']=='REVIEWER_CANNOT_EXECUTE'
    assert calls['count']==0


def test_phase2b_delete_failure_maps_to_execution_failed(
    monkeypatch,
    app_ctx,
):
    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        order,
        _,
        execution,
    )=_phase2b_execution_fixture(
        m,
        'DELETEFAIL',
    )

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_preflight',
        lambda order_arg,*a,**k: _phase2b_allowed_preflight(order_arg),
    )

    def fake_delete_failure(*args,**kwargs):
        assert kwargs.get('preflight',{}).get('allowed') is True
        assert kwargs.get('after_delete') is not None
        return (
            {
                'ok':False,
                'deleted':False,
                'ris_state_updated':False,
                'error':'ORTHANC_DELETE_FAILED',
            },
            502,
        )

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_execute',
        fake_delete_failure,
    )

    with m.app.test_request_context(
        '/correction-center/executions/test/execute',
        method='POST',
    ):
        m.session['uid']=executor.id

        payload,status=m.correction_wrong_images_execute(
            execution.id,
            executor,
            4,
            order.accession,
            'Approved execution reason',
        )

    assert status==502
    assert payload['deleted'] is False

    m.db.session.refresh(execution)

    assert execution.status=='EXECUTION_FAILED'
    assert execution.state_version==7


def test_phase2b_post_delete_failure_maps_to_verification_failed(
    monkeypatch,
    app_ctx,
):
    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        order,
        _,
        execution,
    )=_phase2b_execution_fixture(
        m,
        'VERIFYFAIL',
    )

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_preflight',
        lambda order_arg,*a,**k: _phase2b_allowed_preflight(order_arg),
    )

    def fake_verify_failure(*args,**kwargs):
        assert kwargs.get('preflight',{}).get('allowed') is True
        after_delete=kwargs.get('after_delete')
        assert after_delete is not None
        after_delete()
        return (
            {
                'ok':False,
                'deleted':True,
                'ris_state_updated':False,
                'error':'ORTHANC_STUDY_STILL_PRESENT',
            },
            502,
        )

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_execute',
        fake_verify_failure,
    )

    with m.app.test_request_context(
        '/correction-center/executions/test/execute',
        method='POST',
    ):
        m.session['uid']=executor.id

        payload,status=m.correction_wrong_images_execute(
            execution.id,
            executor,
            4,
            order.accession,
            'Approved execution reason',
        )

    assert status==502
    assert payload['deleted'] is True

    m.db.session.refresh(execution)

    assert execution.status=='VERIFICATION_FAILED'
    assert execution.state_version==8


def test_phase2b_second_execute_attempt_is_blocked(
    monkeypatch,
    app_ctx,
):
    m=app_ctx

    (
        _,
        _,
        _,
        executor,
        _,
        order,
        _,
        execution,
    )=_phase2b_execution_fixture(
        m,
        'SECOND',
    )

    execution.status='COMPLETED'
    execution.state_version=6
    m.db.session.commit()

    calls={'count':0}

    def fail_shared(*args,**kwargs):
        calls['count']+=1
        raise AssertionError(
            'second execution must not reach shared primitive'
        )

    monkeypatch.setattr(
        m,
        'granular_delete_images_only_execute',
        fail_shared,
    )

    payload,status=m.correction_wrong_images_execute(
        execution.id,
        executor,
        6,
        order.accession,
        'Approved execution reason',
    )

    assert status==409
    assert payload['error']=='EXECUTION_NOT_CLAIMED'
    assert calls['count']==0


def test_phase2b_adapter_adds_no_second_requests_delete(
    app_ctx,
):
    import inspect

    m=app_ctx

    adapter=_get_source(
        m.correction_wrong_images_execute
    )

    helper=_get_source(
        m.granular_delete_images_only_execute
    )

    assert 'requests.delete(' not in adapter
    assert helper.count('requests.delete(')==1


def test_phase2b_execute_route_disabled_by_default(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    import uuid
    test_suffix=uuid.uuid4().hex[:10]

    monkeypatch.delenv(
        'RADBRIDGE_CORRECTION_DESTRUCTIVE_EXECUTION_ENABLED',
        raising=False,
    )

    called={'count':0}

    def fake_adapter(*args,**kwargs):
        called['count']+=1
        raise AssertionError(
            'adapter must not run while feature flag is disabled'
        )

    monkeypatch.setattr(
        m,
        'correction_wrong_images_execute',
        fake_adapter,
    )

    client=m.app.test_client()

    super_role=m.Role.query.filter_by(
        code='SUPER_ADMIN'
    ).first()

    user=m.User(
        username=f'phase2b-disabled-route-user-{test_suffix}',
        full_name='Phase2B Disabled Route',
        password_hash='phase2b-test-only-hash',
        role_id=super_role.id,
        active=True,
    )

    m.db.session.add(user)
    m.db.session.commit()

    with client.session_transaction() as sess:
        sess['uid']=user.id

    response=client.post(
        '/correction-center/executions/999/execute',
        data={
            'expected_version':'1',
            'confirm_accession':'TEST',
            'reason':'Valid test reason',
        },
    )

    assert response.status_code==503
    assert called['count']==0


def test_phase2b_execute_route_requires_permission(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    import uuid
    test_suffix=uuid.uuid4().hex[:10]

    monkeypatch.setenv(
        'RADBRIDGE_CORRECTION_DESTRUCTIVE_EXECUTION_ENABLED',
        '1',
    )

    role=m.Role.query.filter_by(
        code='TECHNICIAN'
    ).first()

    user=m.User(
        username=f'phase2b-no-execute-perm-{test_suffix}',
        full_name='Phase2B No Execute Permission',
        password_hash='phase2b-test-only-hash',
        role_id=role.id,
        active=True,
    )

    m.db.session.add(user)
    m.db.session.commit()

    client=m.app.test_client()

    with client.session_transaction() as sess:
        sess['uid']=user.id

    response=client.post(
        '/correction-center/executions/999/execute',
        data={
            'expected_version':'1',
            'confirm_accession':'TEST',
            'reason':'Valid test reason',
        },
    )

    assert response.status_code in (302,403)


def test_phase2b_execute_route_uses_authenticated_actor_only(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    import uuid
    test_suffix=uuid.uuid4().hex[:10]

    monkeypatch.setenv(
        'RADBRIDGE_CORRECTION_DESTRUCTIVE_EXECUTION_ENABLED',
        '1',
    )

    super_role=m.Role.query.filter_by(
        code='SUPER_ADMIN'
    ).first()

    user=m.User(
        username=f'phase2b-route-actor-{test_suffix}',
        full_name='Phase2B Route Actor',
        password_hash='phase2b-test-only-hash',
        role_id=super_role.id,
        active=True,
    )

    m.db.session.add(user)
    m.db.session.commit()

    captured={}

    def fake_adapter(
        execution_id,
        actor,
        expected_version,
        typed_accession,
        reason,
    ):
        captured['execution_id']=execution_id
        captured['actor_id']=actor.id
        captured['expected_version']=expected_version
        captured['typed_accession']=typed_accession
        captured['reason']=reason

        return {
            'ok':False,
            'error':'TEST_BLOCK',
        },409

    monkeypatch.setattr(
        m,
        'correction_wrong_images_execute',
        fake_adapter,
    )

    client=m.app.test_client()

    with client.session_transaction() as sess:
        sess['uid']=user.id

    response=client.post(
        '/correction-center/executions/321/execute',
        data={
            'expected_version':'7',
            'confirm_accession':'RB-321',
            'reason':'Controlled route test reason',
            'actor_id':'999999',
        },
    )

    assert response.status_code==409

    assert captured['execution_id']==321
    assert captured['actor_id']==user.id
    assert captured['expected_version']=='7'
    assert captured['typed_accession']=='RB-321'
    assert captured['reason']=='Controlled route test reason'


def test_phase2b_execute_route_requires_expected_version(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    import uuid
    test_suffix=uuid.uuid4().hex[:10]

    monkeypatch.setenv(
        'RADBRIDGE_CORRECTION_DESTRUCTIVE_EXECUTION_ENABLED',
        '1',
    )

    super_role=m.Role.query.filter_by(
        code='SUPER_ADMIN'
    ).first()

    user=m.User(
        username=f'phase2b-route-version-{test_suffix}',
        full_name='Phase2B Route Version',
        password_hash='phase2b-test-only-hash',
        role_id=super_role.id,
        active=True,
    )

    m.db.session.add(user)
    m.db.session.commit()

    client=m.app.test_client()

    with client.session_transaction() as sess:
        sess['uid']=user.id

    response=client.post(
        '/correction-center/executions/123/execute',
        data={
            'confirm_accession':'RB-123',
            'reason':'Controlled route test reason',
        },
    )

    assert response.status_code==400


def test_phase2b_execute_route_requires_accession_and_reason(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    import uuid
    test_suffix=uuid.uuid4().hex[:10]

    monkeypatch.setenv(
        'RADBRIDGE_CORRECTION_DESTRUCTIVE_EXECUTION_ENABLED',
        '1',
    )

    super_role=m.Role.query.filter_by(
        code='SUPER_ADMIN'
    ).first()

    user=m.User(
        username=f'phase2b-route-form-{test_suffix}',
        full_name='Phase2B Route Form',
        password_hash='phase2b-test-only-hash',
        role_id=super_role.id,
        active=True,
    )

    m.db.session.add(user)
    m.db.session.commit()

    client=m.app.test_client()

    with client.session_transaction() as sess:
        sess['uid']=user.id

    missing_accession=client.post(
        '/correction-center/executions/123/execute',
        data={
            'expected_version':'1',
            'reason':'Controlled route test reason',
        },
    )

    assert missing_accession.status_code==400

    short_reason=client.post(
        '/correction-center/executions/123/execute',
        data={
            'expected_version':'1',
            'confirm_accession':'RB-123',
            'reason':'bad',
        },
    )

    assert short_reason.status_code==400


def test_phase2b_execute_route_contains_no_direct_delete(
    app_ctx,
):
    import inspect

    m=app_ctx

    source=_get_source(
        m.correction_execution_execute_route
    )

    assert 'requests.delete(' not in source
    assert 'granular_delete_images_only_preflight(' not in source
    assert 'pacs_status=' not in source
    assert 'pacs_image_count=' not in source

    assert (
        source.count(
            'correction_wrong_images_execute('
        )
        == 1
    )


def test_phase2b_adapter_must_not_bypass_execution_transition_helper(
    app_ctx,
):
    import inspect

    m=app_ctx

    source=_get_source(
        m.correction_wrong_images_execute
    )

    assert 'correction_execution_transition(' in source

    forbidden=(
        "execution.status='EXECUTING'",
        "execution.status='COMPLETED'",
        "execution.status='EXECUTION_FAILED'",
        "execution.status='VERIFICATION_FAILED'",
    )

    for marker in forbidden:
        assert marker not in source


def test_phase2b_state_machine_requires_preflight_before_executing(
    app_ctx,
):
    m=app_ctx

    assert (
        'EXECUTING'
        not in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'CLAIMED_FOR_EXECUTION'
        ]
    )

    assert (
        'PREFLIGHT_PASSED'
        in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'CLAIMED_FOR_EXECUTION'
        ]
    )

    assert (
        'EXECUTING'
        in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'PREFLIGHT_PASSED'
        ]
    )


def test_phase2b_state_machine_requires_verifying_before_completed(
    app_ctx,
):
    m=app_ctx

    assert (
        'COMPLETED'
        not in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'EXECUTING'
        ]
    )

    assert (
        'VERIFYING'
        in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'EXECUTING'
        ]
    )

    assert (
        'COMPLETED'
        in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'VERIFYING'
        ]
    )


def test_phase2b_failure_states_match_irreversible_boundary(
    app_ctx,
):
    m=app_ctx

    assert (
        'EXECUTION_FAILED'
        in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'EXECUTING'
        ]
    )

    assert (
        'VERIFICATION_FAILED'
        in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'VERIFYING'
        ]
    )

    assert (
        'VERIFICATION_FAILED'
        not in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'EXECUTING'
        ]
    )


def test_phase2b_preflight_block_is_before_destructive_execution(
    app_ctx,
):
    m=app_ctx

    assert (
        'PREFLIGHT_BLOCKED'
        in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'CLAIMED_FOR_EXECUTION'
        ]
    )

    assert (
        'EXECUTING'
        not in
        m.CORRECTION_EXECUTION_TRANSITIONS[
            'PREFLIGHT_BLOCKED'
        ]
    )

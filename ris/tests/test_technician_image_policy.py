from types import SimpleNamespace
import pytest
from technician_image_policy import completion_image_policy


@pytest.fixture(autouse=True)
def isolated_policy_tests(app_ctx,monkeypatch):
    monkeypatch.setattr(app_ctx.db.session,'commit',app_ctx.db.session.flush)
    yield
    app_ctx.db.session.rollback();app_ctx.db.session.remove()


def check(**changes):
    values=dict(matched=True,pacs_present=True,error='',image_count=3,
                policy_defined=True,min_images=2,required_series='AP/LAT',
                series=[{'description':'AP','instance_count':3}])
    values.update(changes)
    return completion_image_policy(**values)


@pytest.mark.parametrize('changes',[
    {'image_count':0}, {'image_count':1}, {'matched':False},
    {'error':'timeout'}, {'pacs_present':False},
    {'series':[{'description':'AP','instance_count':0}]},
    {'series':[{'description':'Other','instance_count':3}]},
])
def test_missing_acquisition_evidence_blocks(changes):
    assert not check(**changes)['allowed']


def test_all_required_series_must_arrive():
    assert not check(required_series='AP,LAT')['allowed']
    assert check(required_series='AP,LAT',series=[
        {'description':'AP','instance_count':2}, {'description':'LAT','instance_count':1}])['allowed']


def test_policyless_exam_allows_confirmed_images_with_warning():
    result=check(policy_defined=False,min_images=0,required_series='',image_count=1)
    assert result['allowed'] and result['warning']
    assert not check(policy_defined=False,min_images=0,required_series='',image_count=0)['allowed']


def test_zero_minimum_never_allows_empty_exam():
    assert not check(min_images=0,image_count=0,required_series='')['allowed']


def test_server_transition_does_not_mutate_or_audit_on_failed_image_check(app_ctx,monkeypatch):
    order=SimpleNamespace(id=998,exam_status='IN_PROGRESS',status='IN_PROGRESS',
                          exam_started_at=None,exam_completed_at=None)
    monkeypatch.setattr(app_ctx,'technician_completion_evidence',lambda _:(check(image_count=0),None))
    decision,old=app_ctx._apply_exam_transition(order,'EXAM_COMPLETED','TECHNICIAN')
    assert not decision.allowed and old=='IN_PROGRESS'
    assert order.exam_status=='IN_PROGRESS' and order.status=='IN_PROGRESS'
    assert order.exam_completed_at is None


def test_start_exam_does_not_require_images(app_ctx,monkeypatch):
    def unexpected(_):raise AssertionError('Start must not check images')
    monkeypatch.setattr(app_ctx,'technician_completion_evidence',unexpected)
    order=SimpleNamespace(exam_status='ORDERED',status='SCHEDULED',exam_started_at=None)
    decision,_=app_ctx._apply_exam_transition(order,'IN_PROGRESS','TECHNICIAN')
    assert decision.allowed and order.exam_status=='IN_PROGRESS'


def test_nursing_cannot_complete_exam(app_ctx,monkeypatch):
    def unexpected(_):raise AssertionError('Denied role must not access acquisition gate')
    monkeypatch.setattr(app_ctx,'technician_completion_evidence',unexpected)
    order=SimpleNamespace(exam_status='IN_PROGRESS',status='IN_PROGRESS')
    decision,_=app_ctx._apply_exam_transition(order,'EXAM_COMPLETED','NURSING')
    assert not decision.allowed


def test_workflow_override_does_not_bypass_images(app_ctx,monkeypatch):
    monkeypatch.setattr(app_ctx,'technician_completion_evidence',lambda _:(check(image_count=0),None))
    order=SimpleNamespace(exam_status='IN_PROGRESS',status='IN_PROGRESS')
    decision,_=app_ctx._apply_exam_transition(order,'EXAM_COMPLETED','SUPER_ADMIN',override=True)
    assert not decision.allowed


@pytest.mark.parametrize('path,status',[
    ('/orders/999998/exam-status','EXAM_COMPLETED'),
    ('/technician/999998/status','COMPLETED'),
    ('/orders/999998/exam-status/override','EXAM_COMPLETED'),
])
def test_direct_http_completion_cannot_bypass_images(app_ctx,monkeypatch,path,status):
    m=app_ctx
    order=SimpleNamespace(id=999998,exam_status='IN_PROGRESS',status='IN_PROGRESS',
                          exam_started_at=None,exam_completed_at=None)
    monkeypatch.setattr(m,'Order',SimpleNamespace(query=SimpleNamespace(get_or_404=lambda _:order)))
    monkeypatch.setattr(m,'current_user',lambda:SimpleNamespace(id=999998,active=True,role=SimpleNamespace(code='SUPER_ADMIN',permissions=lambda:['*'])))
    monkeypatch.setattr(m,'has_perm',lambda _:True)
    monkeypatch.setattr(m,'technician_completion_evidence',lambda _:(check(image_count=0),None))
    def forbidden(*args,**kwargs):pytest.fail('Blocked exam caused an event, stock deduction or assignment')
    for name in ('audit','enqueue_event','coordinate_post_exam_assignment'):
        monkeypatch.setattr(m,name,forbidden)
    monkeypatch.setattr(m.db.session,'commit',forbidden)
    with m.app.test_client() as client:
        response=client.post(path,data={'status':status,'reason':'CODEX UAT override'})
        assert response.status_code==302
    assert order.status==order.exam_status=='IN_PROGRESS' and order.exam_completed_at is None


@pytest.mark.parametrize('role',['RECEPTION','NURSING','RADIOLOGIST','FINANCE'])
def test_image_check_direct_url_requires_technician_permission(app_ctx,monkeypatch,role):
    m=app_ctx
    from test_assignment_distribution import doctor
    user=doctor('CODEX-UAT-image-check-'+role,role)
    monkeypatch.setattr(m,'current_user',lambda:user)
    monkeypatch.setattr(m,'has_perm',lambda _:False)
    with m.app.test_client() as client:
        assert client.post('/technician/999997/check-images').status_code==403


def test_view_permission_cannot_change_acquisition_policy(app_ctx,monkeypatch):
    m=app_ctx
    from test_assignment_distribution import doctor
    user=doctor('CODEX-UAT-policy-viewer','RECEPTION')
    monkeypatch.setattr(m,'current_user',lambda:user)
    monkeypatch.setattr(m,'has_perm',lambda p:p=='users.view')
    with m.app.test_client() as client:
        assert client.get('/admin/procedure-quality-rules').status_code==200
        assert client.post('/admin/procedure-quality-rules',data={'modality':'DX'}).status_code==403


def test_admin_policy_create_edit_notes_and_audit(app_ctx,monkeypatch):
    from test_assignment_distribution import doctor
    m=app_ctx
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    try:
        user=doctor('CODEX-UAT-acquisition-admin','SUPER_ADMIN')
        monkeypatch.setattr(m,'current_user',lambda:user)
        monkeypatch.setattr(m,'has_perm',lambda _:True)
        client=m.app.test_client()
        data={'modality':'DX','procedure_pattern':'CODEX-UAT','min_images':'2','warning_images':'3',
              'required_series':'AP,LAT','active':'1','require_pacs_study':'1','acquisition_notes':'Test positioning instructions'}
        assert client.post('/admin/procedure-quality-rules',data=data).status_code==302
        rule=m.ProcedureQualityRule.query.filter_by(procedure_pattern='CODEX-UAT').one()
        assert rule.min_images==2 and m.technician_acquisition_notes(rule)=='Test positioning instructions'
        assert client.get('/admin/procedure-quality-rules?rule_id='+str(rule.id)).status_code==200
        data.update(rule_id=str(rule.id),min_images='4',acquisition_notes='Updated synthetic notes')
        assert client.post('/admin/procedure-quality-rules',data=data).status_code==302
        assert rule.min_images==4 and m.technician_acquisition_notes(rule)=='Updated synthetic notes'
        assert m.AuditLog.query.filter_by(action='PROCEDURE_QUALITY_POLICY_UPDATE',entity_id=str(rule.id)).count()==2
    finally:
        m.db.session.rollback();m.db.session.remove()


def test_fresh_pacs_error_blocks_even_when_ris_cached_count_is_high(app_ctx,monkeypatch):
    m=app_ctx
    order=SimpleNamespace(id=999996,pacs_image_count=900)
    monkeypatch.setattr(m,'quality_rule_for',lambda _:None)
    monkeypatch.setattr(m,'pacs_demographic_gate',lambda _:(True,'AUTO_SAFE'))
    monkeypatch.setattr(m,'pacs_readiness_evidence',lambda _:(0,{'orthanc_study_id':'synthetic'},'timeout',[]))
    monkeypatch.setattr(m,'CaseReadinessOverride',SimpleNamespace(query=SimpleNamespace(filter_by=lambda **_:SimpleNamespace(first=lambda:None))))
    result,_=m.technician_completion_evidence(order)
    assert not result['allowed'] and result['image_count']==0


def test_case_page_shows_current_policy_not_old_readiness_minimum(app_ctx,monkeypatch):
    from test_assignment_distribution import doctor,order
    m=app_ctx
    user=doctor('CODEX-UAT-policy-display','SUPER_ADMIN')
    o=order('CODEX-UAT-POLICY-DISPLAY','DX');o.procedure='CODEX UAT Display';o.exam_status='IN_PROGRESS'
    rule=m.ProcedureQualityRule(modality='DX',procedure_pattern='CODEX UAT Display',min_images=2,required_series='AP,LAT',active=True)
    m.db.session.add_all([rule,m.CaseReadiness(order_id=o.id,expected_min_images=0,image_count=0)])
    m.db.session.flush();monkeypatch.setattr(m,'current_user',lambda:user)
    with m.app.test_client() as client:
        response=client.get('/technician/'+str(o.id))
        assert response.status_code==200
        assert b'Minimum DICOM images: <b>2</b>' in response.data

import json
from datetime import datetime,timedelta
import pytest
import app as m
import readiness_operations as op
from test_report_template_routes import isolated,client
from test_assignment_distribution import order

@pytest.fixture(autouse=True)
def only_this_test_candidates(isolated):
    # Other modules retain synthetic orders; scope scheduler tests inside the rollback fixture.
    m.Order.query.update({m.Order.status:'CANCELLED'},synchronize_session=False)
    m.db.session.flush()

def token(c):
    assert c.get('/operations/case-readiness').status_code==200
    with c.session_transaction() as s:return s['readiness_csrf']

def enable(**changes):
    config=dict(op.DEFAULTS,enabled=True,**changes)
    m.db.session.add(m.StudioTemplate(template_type='READINESS_AUTOCHECK',name='Synthetic settings',scope='GLOBAL',version_no=1,status='PUBLISHED',layout_json=json.dumps(config)))
    m.db.session.flush()

def fake_evaluate(o):
    row=m.CaseReadiness.query.filter_by(order_id=o.id).first() or m.CaseReadiness(order_id=o.id)
    row.status='READY';row.score=100;row.checked_at=datetime.utcnow();row.image_count=1;row.expected_min_images=1
    row.details_json=json.dumps({'blockers':[]});row.missing_pacs=False
    m.db.session.add(row);m.db.session.flush();return row

@pytest.mark.parametrize('key,value',[('XRAY',59),('CT',3601),('MR','nan'),('batch_limit',0),('batch_limit',21)])
def test_invalid_schedule_rejected(key,value):
    with pytest.raises(ValueError):op.validate_settings(dict(op.DEFAULTS,**{key:value}))

def test_schedule_permission_csrf_version_and_audit():
    c,u=client();t=token(c)
    assert c.post('/operations/case-readiness/settings',data={'enabled':'1'}).status_code==400
    assert c.post('/operations/case-readiness/settings',data={'csrf_token':t,'enabled':'1','XRAY':'180'}).status_code==302
    assert c.post('/operations/case-readiness/settings',data={'csrf_token':t,'XRAY':'240'}).status_code==302
    rows=m.StudioTemplate.query.filter_by(template_type='READINESS_AUTOCHECK').order_by(m.StudioTemplate.id).all()
    assert [r.version_no for r in rows]==[1,2]
    assert json.loads(rows[0].layout_json)['enabled'] and not json.loads(rows[1].layout_json)['enabled']
    assert m.StudioTemplateVersion.query.filter(m.StudioTemplateVersion.template_id.in_([r.id for r in rows])).count()==2
    assert m.AuditLog.query.filter_by(action='READINESS_SCHEDULE_UPDATED').count()==2

def test_schedule_starts_paused_and_does_no_checks(monkeypatch):
    order('CODEX-UAT-READINESS-PAUSED')
    monkeypatch.setattr(m,'evaluate_case_readiness',lambda o:pytest.fail('Paused worker queried PACS'))
    assert op.run_due(m)=={'enabled':False,'checked':0,'errors':0}

def test_due_checks_use_modality_intervals_and_skip_final(monkeypatch):
    enable();now=datetime.utcnow()
    due=order('CODEX-UAT-DUE-DX',modality='DX')
    recent=order('CODEX-UAT-RECENT-CT',modality='CT')
    closed=order('CODEX-UAT-CLOSED-DX',modality='DX');m.get_report(closed).status='FINAL'
    fake_evaluate(due).checked_at=now-timedelta(seconds=130)
    fake_evaluate(recent).checked_at=now-timedelta(seconds=130)
    m.db.session.flush();monkeypatch.setattr(m,'evaluate_case_readiness',fake_evaluate)
    result=op.run_due(m,now)
    assert result['checked']==1
    assert m.CaseReadiness.query.filter_by(order_id=recent.id).one().checked_at==now-timedelta(seconds=130)
    assert not m.CaseReadiness.query.filter_by(order_id=closed.id).first()

def test_batch_limit_and_oldest_first(monkeypatch):
    enable(batch_limit=1);one=order('CODEX-UAT-OLDEST');two=order('CODEX-UAT-NEWEST')
    monkeypatch.setattr(m,'evaluate_case_readiness',fake_evaluate)
    assert op.run_due(m)['checked']==1
    assert m.CaseReadiness.query.filter_by(order_id=one.id).first()
    assert not m.CaseReadiness.query.filter_by(order_id=two.id).first()

def test_pacs_error_never_makes_case_ready(monkeypatch):
    o=order('CODEX-UAT-PACS-FAIL')
    def failed(o):
        r=fake_evaluate(o);r.details_json=json.dumps({'pacs_error':'Unavailable','blockers':[]});return r
    monkeypatch.setattr(m,'evaluate_case_readiness',failed)
    assert op.refresh(m,o).status=='BLOCKED'
    assert m.CaseReadiness.query.filter_by(order_id=o.id).one().missing_pacs

def test_manual_check_is_audited_and_final_is_immutable(monkeypatch):
    c,u=client();o=order('CODEX-UAT-MANUAL');t=token(c)
    monkeypatch.setattr(m,'evaluate_case_readiness',fake_evaluate)
    assert c.post(f'/orders/{o.id}/readiness/check',data={'csrf_token':t}).status_code==302
    assert m.AuditLog.query.filter_by(action='CASE_READINESS_RECHECKED').count()==1
    m.get_report(o).status='FINAL';m.db.session.flush()
    assert c.post(f'/orders/{o.id}/readiness/check',data={'csrf_token':t}).status_code==409
    assert m.AuditLog.query.filter_by(action='CASE_READINESS_RECHECKED').count()==1

def test_view_only_user_cannot_recheck_or_change_settings():
    c,u=client('RECEPTION');u.role.permissions_json=json.dumps(['orders.view']);m.db.session.flush()
    o=order('CODEX-UAT-READONLY');t=token(c)
    assert c.post(f'/orders/{o.id}/readiness/check',data={'csrf_token':t}).status_code==403
    assert c.post('/operations/case-readiness/settings',data={'csrf_token':t}).status_code==403

def test_branch_filter_and_cross_branch_recheck_denied(monkeypatch):
    c,u=client('TECHNICIAN');u.role.permissions_json=json.dumps(['orders.view','orders.status'])
    b=m.Branch(name='Synthetic branch',code='CODEX-UAT-READY-BR');m.db.session.add(b);m.db.session.flush();u.branch_id=b.id
    o=order('CODEX-UAT-OTHER-BRANCH');o.branch_id=None;m.db.session.flush()
    t=token(c)
    assert b'CODEX-UAT-OTHER-BRANCH' not in c.get('/operations/case-readiness').data
    assert c.post(f'/orders/{o.id}/readiness/check',data={'csrf_token':t}).status_code==403

def test_repeated_check_does_not_duplicate_notifications(monkeypatch):
    c,u=client();o=order('CODEX-UAT-NOTIFY');t=token(c)
    def incomplete(o):r=fake_evaluate(o);r.incomplete_images=True;r.status='BLOCKED';return r
    monkeypatch.setattr(m,'evaluate_case_readiness',incomplete)
    for i in range(2):assert c.post(f'/orders/{o.id}/readiness/check',data={'csrf_token':t}).status_code==302
    assert m.RISNotification.query.filter_by(order_id=o.id,event_type='INCOMPLETE_IMAGES',status='NEW').count()==1

def test_invalid_published_settings_fail_closed():
    m.db.session.add(m.StudioTemplate(template_type='READINESS_AUTOCHECK',name='Invalid synthetic',scope='GLOBAL',status='PUBLISHED',layout_json='INVALID'))
    m.db.session.flush()
    with pytest.raises(ValueError):op.run_due(m)

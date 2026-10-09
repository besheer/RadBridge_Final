from types import SimpleNamespace
from unittest.mock import Mock
import pytest

@pytest.fixture
def scope_fixture(app_ctx, monkeypatch):
    m=app_ctx
    user=SimpleNamespace(id=91,active=True,branch_id=2,role=SimpleNamespace(code='TECHNICIAN',permissions=lambda:['technician.worklist','orders.status','workflow.override']))
    order=SimpleNamespace(id=987,branch_id=2,status='SCHEDULED',exam_status='ORDERED',exam_started_at=None,exam_completed_at=None,accession='CODEX-UAT-SCOPE')
    monkeypatch.setattr(m,'current_user',lambda:user)
    monkeypatch.setattr(m,'render_template',lambda *a,**kw:'CODEX UAT error page')
    monkeypatch.setattr(type(m.Order.query),'get_or_404',lambda self,oid:order)
    monkeypatch.setattr(m,'audit',Mock())
    monkeypatch.setattr(m,'enqueue_event',Mock())
    monkeypatch.setattr(m.db.session,'commit',Mock())
    transition=Mock(return_value=(SimpleNamespace(allowed=True),'ORDERED'))
    monkeypatch.setattr(m,'_apply_exam_transition',transition)
    return m,user,order,transition

ROUTES=[('/orders/987/exam-status','IN_PROGRESS'),('/technician/987/status','IN_PROGRESS'),('/technician/987/status','ARRIVED'),('/orders/987/exam-status/override','IN_PROGRESS')]

@pytest.mark.parametrize('route,status',ROUTES)
@pytest.mark.parametrize('boundary',['other_branch','unscoped_user','inactive'])
def test_scope_denial_precedes_transition_audit_or_mutation(scope_fixture,route,status,boundary):
    m,user,order,transition=scope_fixture
    if boundary=='other_branch':order.branch_id=3
    if boundary=='unscoped_user':user.branch_id=None
    if boundary=='inactive':user.active=False
    with m.app.test_client() as client:
        response=client.post(route,data={'status':status,'reason':'CODEX UAT scope test'})
    assert response.status_code==403
    assert order.status=='SCHEDULED' and order.exam_status=='ORDERED'
    assert order.exam_started_at is None
    transition.assert_not_called();m.audit.assert_not_called();m.enqueue_event.assert_not_called();m.db.session.commit.assert_not_called()

@pytest.mark.parametrize('route,status',ROUTES)
def test_same_branch_actions_keep_existing_workflow(scope_fixture,route,status):
    m,user,order,transition=scope_fixture
    with m.app.test_client() as client:
        response=client.post(route,data={'status':status,'reason':'CODEX UAT scope test'})
    assert response.status_code==302
    m.db.session.commit.assert_called_once()
    if status=='ARRIVED':assert order.status=='ARRIVED'
    else:transition.assert_called_once()


def test_explicit_global_supervisor_access_is_preserved(scope_fixture):
    m,user,order,transition=scope_fixture
    user.role.code='SUPER_ADMIN';user.branch_id=None;order.branch_id=3
    with m.app.test_client() as client:
        response=client.post('/orders/987/exam-status/override',data={'status':'IN_PROGRESS','reason':'CODEX UAT supervisor action'})
    assert response.status_code==302
    transition.assert_called_once();m.db.session.commit.assert_called_once()

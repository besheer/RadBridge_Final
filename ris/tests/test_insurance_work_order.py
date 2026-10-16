"""Isolated ORM tests; never send a real Worklist or change live finances."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest


@pytest.fixture
def insurance_case(app_ctx, monkeypatch):
    m = app_ctx
    key = 'CODEX-UAT-' + uuid4().hex[:8]
    branch = m.Branch(code=key, name=key, active=True)
    patient = m.Patient(patient_id=key, name='CODEX UAT INSURANCE', dob='19900101', sex='M')
    contract = m.Contract(code=key, name=key, approval_required=True)
    m.db.session.add_all([branch, patient, contract]); m.db.session.flush()
    device = m.Device(branch_id=branch.id, name=key, modality='DX', ae_title='CODEX_UAT')
    m.db.session.add(device); m.db.session.flush()
    order = m.Order(accession=key, patient_id=patient.id, branch_id=branch.id,
                    contract_id=contract.id, device_id=device.id, modality='DX',
                    procedure='CODEX UAT Chest', station_ae=device.ae_title,
                    scheduled=datetime(2037, 2, 3, 10), status='REGISTERED',
                    patient_share=100, paid_amount=100, exam_status='BOOKED')
    m.db.session.add(order); m.db.session.flush()
    stored_user=m.User(username=key,full_name='Synthetic Insurance Reception',password_hash='disabled-test-account',
                       active=True,branch_id=branch.id,role=m.Role.query.filter_by(code='RECEPTION').one())
    m.db.session.add(stored_user);m.db.session.flush()
    user = SimpleNamespace(id=stored_user.id, username=key, active=True, branch_id=branch.id,
         role=SimpleNamespace(code='RECEPTION', permissions=lambda: m.ROLE_PERMS['RECEPTION']))
    monkeypatch.setattr(m, 'current_user', lambda: user)
    monkeypatch.setattr(m, 'render_template', lambda *a, **k: 'CODEX UAT error')
    monkeypatch.setattr(m.db.session, 'commit', m.db.session.flush)
    real_sender=m.send_mwl
    monkeypatch.setattr(m, 'send_mwl', Mock(return_value={'ID': 'CODEX-UAT'}))
    yield SimpleNamespace(m=m, order=order, user=user, contract=contract, real_sender=real_sender)
    m.db.session.rollback(); m.db.session.remove()


def post(c, action, data=None):
    return c.m.app.test_client().post(f'/orders/{c.order.id}/{action}', data=data or {})


def approval(c, status='PENDING', reference=''):
    row = c.m.InsuranceApprovalRequest(order_id=c.order.id, status=status, approval_no=reference)
    c.m.db.session.add(row); c.m.db.session.flush()
    return row


@pytest.mark.parametrize('role', ['TECHNICIAN','NURSING','RADIOLOGIST','CASE_COORDINATOR','CASHIER'])
@pytest.mark.parametrize('action', ['start','update'])
def test_view_permission_cannot_change_insurance(insurance_case, role, action):
    c=insurance_case; row=approval(c)
    c.user.role=SimpleNamespace(code=role, permissions=lambda: c.m.ROLE_PERMS[role])
    before=c.m.AuditLog.query.count()
    assert post(c, 'insurance-approval/'+action, {'status':'APPROVED','approval_no':'CODEX-UAT'}).status_code==403
    assert row.status=='PENDING'
    assert c.m.InsuranceApprovalRequest.query.filter_by(order_id=c.order.id).count()==1
    assert c.m.InsuranceApprovalEvent.query.filter_by(approval_request_id=row.id).count()==0
    assert c.m.AuditLog.query.count()==before


@pytest.mark.parametrize('boundary',['other_branch','no_branch','inactive'])
@pytest.mark.parametrize('action',['start','update'])
def test_actor_branch_boundary(insurance_case,boundary,action):
    c=insurance_case;row=approval(c)
    if boundary=='other_branch': c.user.branch_id=c.order.branch_id+10000
    if boundary=='no_branch': c.user.branch_id=None
    if boundary=='inactive': c.user.active=False
    assert post(c,'insurance-approval/'+action,{'status':'APPROVED','approval_no':'CODEX-UAT'}).status_code==403
    assert row.status=='PENDING'


@pytest.mark.parametrize('role',['RECEPTION','CONTRACTS','SUPER_ADMIN'])
def test_authorized_approval_records_decision_and_audit(insurance_case,role):
    c=insurance_case;row=approval(c)
    c.user.role=SimpleNamespace(code=role,permissions=lambda:c.m.ROLE_PERMS[role])
    if role=='SUPER_ADMIN': c.user.branch_id=None
    assert post(c,'insurance-approval/update',{'status':'APPROVED','approval_no':'CODEX-UAT'}).status_code==302
    assert row.status=='APPROVED' and row.approval_no==c.order.approval_no=='CODEX-UAT'
    assert c.m.InsuranceApprovalEvent.query.filter_by(approval_request_id=row.id,event_type='STATUS_CHANGE').count()==1
    assert c.m.AuditLog.query.filter_by(entity_id=str(c.order.id),action='INSURANCE_APPROVAL_UPDATE').count()==1


def test_blank_approval_is_rejected_and_unresolved_decision_clears_reference(insurance_case):
    c=insurance_case;row=approval(c)
    assert post(c,'insurance-approval/update',{'status':'APPROVED','approval_no':'  '}).status_code==302
    assert row.status=='PENDING'
    row.status='APPROVED';row.approval_no=c.order.approval_no='CODEX-UAT'
    assert post(c,'insurance-approval/update',{'status':'NEED_INFO'}).status_code==302
    assert row.status=='NEED_INFO' and not c.order.approval_no


@pytest.mark.parametrize('status',[None,'REQUIRED','PENDING','SUBMITTED','REJECTED','NEED_INFO','ERROR','NOT_REQUIRED','APPROVED'])
def test_paid_order_cannot_bypass_incomplete_approval(insurance_case,status):
    c=insurance_case
    if status:approval(c,status)
    c.order.approval_no='LEGACY_REFERENCE_ONLY'
    before=c.m.EventOutbox.query.count()
    assert post(c,'convert-to-work-order').status_code==302
    assert c.order.status=='REGISTERED' and c.order.exam_status=='BOOKED'
    assert c.m.EventOutbox.query.count()==before
    c.m.send_mwl.assert_not_called()
    assert c.m.AuditLog.query.filter_by(entity_id=str(c.order.id),action='WORK_ORDER_BLOCKED').count()==1


@pytest.mark.parametrize('insured',[True,False])
def test_ready_order_keeps_existing_conversion_flow(insurance_case,insured):
    c=insurance_case
    if insured:approval(c,'APPROVED','CODEX-UAT')
    else:c.order.contract_id=None;c.order.contract=None
    assert post(c,'convert-to-work-order').status_code==302
    assert c.order.status=='SCHEDULED' and c.order.exam_status=='ORDERED'
    c.m.send_mwl.assert_called_once_with(c.order)


def test_latest_decision_and_actual_outbound_gate(insurance_case,monkeypatch):
    import insurance_policy
    import application.legacy_runtime as legacy_runtime
    c=insurance_case
    approval(c,'APPROVED','CODEX-UAT');approval(c,'PENDING')
    assert insurance_policy.approval_blocker(c.order,runtime=c.m)
    monkeypatch.setattr(legacy_runtime,'resolve_runtime',lambda: (_ for _ in ()).throw(
        AssertionError('insurance gate must use explicitly supplied runtime')))
    network=Mock(side_effect=AssertionError('Incomplete approval must not leave RIS'))
    monkeypatch.setattr(c.m.requests,'post',network)
    with pytest.raises(ValueError): c.real_sender(c.order)
    network.assert_not_called()


def test_insurance_route_authorization_uses_composed_runtime(insurance_case,monkeypatch):
    import application.legacy_runtime as legacy_runtime
    c=insurance_case
    monkeypatch.setattr(legacy_runtime,'resolve_runtime',lambda: (_ for _ in ()).throw(
        AssertionError('insurance route must use explicitly supplied runtime')))
    response=post(c,'insurance-approval/start',{'method':'MANUAL'})
    assert response.status_code==302
    assert c.m.InsuranceApprovalRequest.query.filter_by(order_id=c.order.id).count()==1

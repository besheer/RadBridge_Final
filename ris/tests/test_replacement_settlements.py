"""Isolated payable adjustments, immutable cash history and boundary tests."""
import json
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
import replacement_settlements as s


@pytest.fixture
def settlement_case(app_ctx, monkeypatch):
    m = app_ctx
    key = 'UAT-SET-' + uuid4().hex[:10]
    role = m.Role.query.filter_by(code='CASE_COORDINATOR').one()
    role.permissions_json = json.dumps(['finance.doctor_share.view', 'finance.doctor_share.manage', 'financial.view'])
    branch = m.Branch(code=key, name=key)
    other = m.Branch(code=key+'X', name=key+'X')
    m.db.session.add_all([branch, other]);m.db.session.flush()
    actor = m.User(username=key+'F', full_name=key+'F', password_hash='disabled', role_id=role.id, branch_id=branch.id, active=True)
    docs = [m.User(username=key+'D'+str(i), full_name=key+'D'+str(i), password_hash='disabled', active=True,
                   role_id=m.Role.query.filter_by(code='RADIOLOGIST').one().id, branch_id=branch.id) for i in range(3)]
    patient = m.Patient(patient_id=key, name='CODEX UAT SETTLEMENT')
    m.db.session.add_all([actor, patient]+docs);m.db.session.flush()
    order = m.Order(accession=key, patient_id=patient.id, branch_id=branch.id, modality='DX', procedure='CODEX UAT',
                    scheduled=datetime(2038,1,1),
                    status='FINAL', assigned_doctor_id=docs[0].id, gross_price=200, contract_price=200, patient_share=200)
    m.db.session.add(order);m.db.session.flush()
    m.db.session.add(m.OrderPerformingDoctor(order_id=order.id, doctor_user_id=docs[0].id))
    report = m.Report(order_id=order.id, status='FINAL', finalized_at=datetime(2038, 1, 1))
    m.db.session.add(report);m.db.session.flush()
    original = m.ReportVersion(report_id=report.id, accession=key, version_no=1, action='FINALIZE',
                                status='VERIFIED', finalized_at=datetime(2038, 1, 1), sha256='0'*64)
    m.db.session.add(original);m.db.session.flush()
    revision = m.ReportRevision(order_id=order.id, original_report_id=report.id, original_version_id=original.id,
        original_sha256='0'*64, base_sha256='0'*64, revision_no=1, kind='REPLACEMENT', reason='CODEX UAT request',
        requested_by=docs[0].id, doctor_id=docs[1].id, status='FINAL', finalized_at=datetime(2038, 2, 1))
    m.db.session.add(revision);m.db.session.flush()
    version = m.ReportRevisionVersion(report_id=revision.id, accession=key, version_no=1,
        action='FINALIZE', status='VERIFIED', finalized_at=datetime(2038, 2, 1), sha256='1'*64)
    rules = [m.PerformingDoctorShareRule(doctor_user_id=docs[1].id, branch_id=branch.id, rule_type='PERCENT', basis='GROSS', value=25),
             m.PerformingDoctorShareRule(doctor_user_id=docs[2].id, branch_id=branch.id, rule_type='FIXED', basis='GROSS', value=30)]
    payout = m.FinancialEntry(entry_type='DOCTOR_FEE', amount=20, user_id=docs[0].id,
                            branch_id=branch.id, reference_no=key, status='POSTED', entry_date=datetime(2038, 1, 15).date())
    m.db.session.add_all([version, payout]+rules);m.db.session.flush()
    monkeypatch.setattr(m, 'current_user', lambda: actor)
    monkeypatch.setattr(m.db.session, 'commit', m.db.session.flush)
    with m.app.test_request_context('/finance/replacement-settlements'):
        yield NS(m=m, actor=actor, docs=docs, branch=branch, other=other, order=order,
                 report=report, revision=revision, version=version, rules=rules, payout=payout,
                 original=original, client=m.app.test_client(), cash_count=m.FinancialEntry.query.count())
    m.db.session.rollback();m.db.session.remove()


def preview(c, **kwargs):
    data = dict(original_amount='40.00', reason='CODEX UAT finance verified original entitlement',
                payments_verified=True, paid_amount='20.00', payment_note='')
    data.update(kwargs)
    return s.preview(c.m, c.revision, **data)


def book(c, **kwargs):
    data, token = preview(c, **kwargs)
    row, retry = s.confirm(c.m, token)
    assert not retry
    c.m.db.session.flush()
    return row, data, token


def test_transfer_uses_replacement_rule_and_retains_originals(settlement_case):
    c=settlement_case;row,data,_=book(c)
    assert row.old_amount==Decimal('40') and row.new_amount==Decimal('50')
    assert row.verified_paid_amount==Decimal('20') and data['recovery_adjustment']=='20.00'
    assert c.payout.amount==Decimal('20') and c.payout.status=='POSTED'
    assert c.order.assigned_doctor_id==c.docs[0].id and c.order.status==c.report.status=='FINAL'
    assert c.m.OrderPerformingDoctor.query.filter_by(order_id=c.order.id).one().doctor_user_id==c.docs[0].id
    assert c.m.FinancialEntry.query.count()==c.cash_count
    assert c.m.AuditLog.query.filter_by(action='REPLACEMENT_ENTITLEMENT_TRANSFER').count()==1
    assert c.m.performing_doctor_share_for_order(c.order)[0:1]==(50.0,)
    assert c.m.performing_doctor_share_for_order(c.order)[2].id==c.docs[1].id


def test_replay_is_idempotent(settlement_case):
    c=settlement_case;row,_,token=book(c)
    again,retry=s.confirm(c.m,token)
    assert retry and again.id==row.id
    assert c.m.ReplacementSettlement.query.count()==1
    assert c.m.AuditLog.query.filter_by(action='REPLACEMENT_ENTITLEMENT_TRANSFER').count()==1


@pytest.mark.parametrize('kind,status,finalized', [('ADDENDUM','FINAL',True),('REPLACEMENT','DRAFT',False),('REPLACEMENT','VERIFIED',False),('REPLACEMENT','FINAL',False)])
def test_only_final_replacement_can_transfer(settlement_case,kind,status,finalized):
    c=settlement_case;c.revision.kind=kind;c.revision.status=status
    if not finalized:c.revision.finalized_at=None
    c.m.db.session.flush()
    with pytest.raises(s.SettlementError,match='FINAL_REPLACEMENT_ONLY'):preview(c)
    assert c.m.ReplacementSettlement.query.count()==0


@pytest.mark.parametrize('value',['NaN','Infinity','-1','10000000000','not-a-number',''])
def test_invalid_original_amount_rejected(settlement_case,value):
    with pytest.raises(s.SettlementError,match='INVALID_MONEY'):preview(settlement_case,original_amount=value)


def test_unlinked_payout_requires_documented_evidence(settlement_case):
    c=settlement_case
    with pytest.raises(s.SettlementError,match='PAYMENTS_NOT_VERIFIED'):preview(c,paid_amount='30')
    row,data,_=book(c,paid_amount='30',payment_note='CODEX UAT bulk payout reference PAYROLL-123')
    assert row.linked_paid_amount==20 and row.verified_paid_amount==30
    assert data['recovery_adjustment']=='30.00' and c.payout.amount==20


def test_paid_total_cannot_omit_linked_entries(settlement_case):
    with pytest.raises(s.SettlementError,match='PAYMENTS_NOT_VERIFIED'):preview(settlement_case,paid_amount='19')


def test_payments_need_explicit_verification(settlement_case):
    with pytest.raises(s.SettlementError,match='PAYMENTS_NOT_VERIFIED'):preview(settlement_case,payments_verified=False)


@pytest.mark.parametrize('change',['rule','payout','version','status'])
def test_preview_invalidated_when_evidence_changes(settlement_case,change):
    c=settlement_case;_,token=preview(c)
    if change=='rule':c.rules[0].value=35
    if change=='payout':c.payout.amount=21
    if change=='version':c.version.sha256='9'*64
    if change=='status':c.revision.status='DRAFT'
    c.m.db.session.flush()
    with pytest.raises(s.SettlementError):s.confirm(c.m,token)
    assert c.m.ReplacementSettlement.query.count()==0


def test_snapshot_stays_frozen_when_rules_change(settlement_case):
    c=settlement_case;row,_,_=book(c);c.rules[0].value=75;c.m.db.session.flush()
    assert c.m.performing_doctor_share_for_order(c.order)[0]==50
    assert Decimal(json.loads(row.snapshot_json)['new_rule']['value'])==25


def test_same_doctor_is_not_a_transfer(settlement_case):
    c=settlement_case;c.revision.doctor_id=c.docs[0].id;c.m.db.session.flush()
    with pytest.raises(s.SettlementError,match='NO_PHYSICIAN_CHANGE'):preview(c)


@pytest.mark.parametrize('mode',['missing','ambiguous','invalid'])
def test_fail_closed_rule_selection(settlement_case,mode):
    c=settlement_case
    if mode=='missing':c.rules[0].active=False
    if mode=='invalid':c.rules[0].value=101
    if mode=='ambiguous':c.m.db.session.add(c.m.PerformingDoctorShareRule(doctor_user_id=c.docs[1].id,branch_id=c.branch.id,rule_type='FIXED',basis='GROSS',value=10))
    c.m.db.session.flush()
    with pytest.raises(s.SettlementError,match={'missing':'MISSING_RULE','ambiguous':'AMBIGUOUS_RULE','invalid':'INVALID_RULE'}[mode]):preview(c)


def test_decimal_percentage_precision(settlement_case):
    c=settlement_case;c.rules[0].value=.125;c.m.db.session.flush()
    assert preview(c)[0]['new_amount']=='0.25'


@pytest.mark.parametrize('mode',['branch','inactive','permission','branchless'])
def test_scope_and_authority(settlement_case,mode):
    c=settlement_case
    if mode=='branch':c.actor.branch_id=c.other.id
    if mode=='inactive':c.actor.active=False
    if mode=='permission':c.actor.role.permissions_json='["finance.doctor_share.view"]'
    if mode=='branchless':c.actor.branch_id=None
    from werkzeug.exceptions import Forbidden
    with pytest.raises(Forbidden):preview(c)


def test_original_financial_owner_is_not_guessed(settlement_case):
    c=settlement_case;c.m.OrderPerformingDoctor.query.filter_by(order_id=c.order.id).delete();c.m.db.session.flush()
    with pytest.raises(s.SettlementError,match='ORIGINAL_DOCTOR_UNKNOWN'):preview(c)


def second_revision(c):
    r=c.m.ReportRevision(order_id=c.order.id,original_report_id=c.report.id,original_version_id=c.original.id,
        original_sha256='0'*64,base_sha256='1'*64,base_revision_id=c.revision.id,revision_no=2,kind='REPLACEMENT',
        reason='CODEX UAT second correction',requested_by=c.docs[1].id,doctor_id=c.docs[2].id,status='FINAL',finalized_at=datetime(2038,3,1))
    c.m.db.session.add(r);c.m.db.session.flush()
    c.m.db.session.add(c.m.ReportRevisionVersion(report_id=r.id,accession=c.order.accession,version_no=1,
        action='FINALIZE',status='VERIFIED',finalized_at=datetime(2038,3,1),sha256='2'*64))
    c.m.db.session.flush();return r


def test_sequential_transfers_reverse_frozen_previous_allocation(settlement_case):
    c=settlement_case;first,_,_=book(c);r=second_revision(c)
    data,token=s.preview(c.m,r,'999','CODEX UAT verified second settlement',True,'0')
    second,_=s.confirm(c.m,token)
    assert second.previous_id==first.id and second.old_doctor_id==c.docs[1].id
    assert second.old_amount==50 and second.new_amount==30
    assert c.m.performing_doctor_share_for_order(c.order)[0]==30
    assert c.payout.amount==20 and c.m.ReplacementSettlement.query.count()==2


def test_previous_replacement_must_be_settled_first(settlement_case):
    c=settlement_case;r=second_revision(c)
    with pytest.raises(s.SettlementError,match='PREVIOUS_REPLACEMENT_UNSETTLED'):
        s.preview(c.m,r,'40','CODEX UAT second settlement',True,'20')


def test_cash_guard_rejects_old_owner_and_pending_transfer(settlement_case):
    c=settlement_case
    from werkzeug.exceptions import Conflict,Forbidden
    with pytest.raises(Conflict):s.guard_case_payout(c.m,c.branch.id,c.docs[0].id,c.order.accession)
    book(c)
    with pytest.raises(Conflict):s.guard_case_payout(c.m,c.branch.id,c.docs[0].id,c.order.accession)
    s.guard_case_payout(c.m,c.branch.id,c.docs[1].id,c.order.accession)
    with pytest.raises(Forbidden):s.guard_case_payout(c.m,c.other.id,c.docs[1].id,c.order.accession)


def test_settlement_history_cannot_be_rewritten(settlement_case):
    c=settlement_case;row,_,_=book(c);row.new_amount=99
    with pytest.raises(s.SettlementError,match='IMMUTABLE'):c.m.db.session.flush()


def test_preview_is_read_only(settlement_case):
    c=settlement_case;before=(c.m.FinancialEntry.query.count(),c.m.AuditLog.query.count())
    preview(c)
    assert before==(c.m.FinancialEntry.query.count(),c.m.AuditLog.query.count())
    assert c.m.ReplacementSettlement.query.count()==0


def test_get_renders_and_post_requires_csrf(settlement_case):
    c=settlement_case
    assert c.client.get('/finance/replacement-settlements',base_url='https://localhost').status_code==200
    response=c.client.post('/finance/replacement-settlements',base_url='https://localhost',data={'action':'preview','revision_id':c.revision.id})
    assert response.status_code==200 and c.m.ReplacementSettlement.query.count()==0


def test_view_only_user_cannot_post(settlement_case):
    c=settlement_case;c.actor.role.permissions_json='["finance.doctor_share.view"]'
    assert c.client.get('/finance/replacement-settlements',base_url='https://localhost').status_code==200
    assert c.client.post('/finance/replacement-settlements',base_url='https://localhost').status_code==403


def test_preview_confirm_route_and_repeat_preserve_cash(settlement_case):
    import html
    import re
    c=settlement_case
    with c.client.session_transaction() as state:
        state['uid']=c.actor.id;state['replacement_settlement_csrf']='CODEX-UAT-CSRF'
    response=c.client.post('/finance/replacement-settlements',base_url='https://localhost',data={
        'action':'preview','csrf':'CODEX-UAT-CSRF','revision_id':c.revision.id,
        'original_amount':'40','paid_amount':'20','payments_verified':'1',
        'reason':'CODEX UAT authorized finance verification'})
    assert response.status_code==200 and c.m.ReplacementSettlement.query.count()==0
    token=html.unescape(re.search(r'name="preview_token" value="([^"]+)"',response.get_data(as_text=True)).group(1))
    post={'action':'confirm','csrf':'CODEX-UAT-CSRF','preview_token':token}
    assert c.client.post('/finance/replacement-settlements',base_url='https://localhost',data=post).status_code==303
    assert c.client.post('/finance/replacement-settlements',base_url='https://localhost',data=post).status_code==303
    assert c.m.ReplacementSettlement.query.count()==1 and c.payout.status=='POSTED' and c.payout.amount==20


def test_earnings_follow_frozen_allocation_and_scope(settlement_case):
    c=settlement_case;book(c)
    response=c.client.get('/finance/doctor-earnings?start=2038-01-01&end=2038-01-31',base_url='https://localhost')
    assert response.status_code==200 and c.docs[1].full_name.encode() in response.data
    assert c.client.get('/finance/doctor-earnings?branch_id='+str(c.other.id),base_url='https://localhost').status_code==403


def test_unpaid_and_fully_paid_adjustments_are_explicit(settlement_case):
    c=settlement_case;c.payout.status='VOID';c.m.db.session.flush()
    data,_=preview(c,paid_amount='0')
    assert data['recovery_adjustment']=='0.00'
    c.payout.status='POSTED';c.payout.amount=40;c.m.db.session.flush()
    data,_=preview(c,paid_amount='40')
    assert data['recovery_adjustment']=='40.00'

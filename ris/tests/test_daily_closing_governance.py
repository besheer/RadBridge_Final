"""Isolated financial boundaries and receipt/refund accounting dates."""
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4
import pytest


@pytest.fixture
def closing_case(app_ctx, monkeypatch):
    m=app_ctx; key='CODEX-UAT-'+uuid4().hex[:8]
    a=m.Branch(code=key+'A',name=key+'A',active=True,reception_collection_enabled=True)
    b=m.Branch(code=key+'B',name=key+'B',active=True)
    p=m.Patient(patient_id=key,name='CODEX UAT CLOSING',dob='19900101',sex='M')
    m.db.session.add_all([a,b,p]);m.db.session.flush()
    o=m.Order(accession=key,patient_id=p.id,branch_id=a.id,modality='DX',procedure=key,
              scheduled=datetime(2037,2,3,10),status='REGISTERED')
    m.db.session.add(o);m.db.session.flush()
    cashier=m.Role.query.filter_by(code='CASHIER').first()
    if cashier is None:
        import json
        cashier=m.Role(code='CASHIER',name='Synthetic Cashier',permissions_json=json.dumps(m.ROLE_PERMS['CASHIER']))
        m.db.session.add(cashier);m.db.session.flush()
    actor=m.User(username=key,full_name='Synthetic Closing Cashier',password_hash='disabled-test-account',
                 active=True,branch_id=a.id,role=cashier)
    m.db.session.add(actor);m.db.session.flush()
    u=SimpleNamespace(id=actor.id,username=key,active=True,branch_id=a.id,
        role=SimpleNamespace(code='CASHIER',permissions=lambda:m.ROLE_PERMS['CASHIER']))
    context={}
    def render(name,**kw):context.clear();context.update(kw);return 'CODEX UAT '+name
    monkeypatch.setattr(m,'current_user',lambda:u)
    monkeypatch.setattr(m,'render_template',render)
    monkeypatch.setattr(m.db.session,'commit',m.db.session.flush)
    yield SimpleNamespace(m=m,a=a,b=b,order=o,user=u,context=context)
    m.db.session.rollback();m.db.session.remove()


def role(c,code):c.user.role=SimpleNamespace(code=code,permissions=lambda:c.m.ROLE_PERMS[code])


def request(c,method='get',branch=None,**changes):
    values={'branch_id':c.a.id if branch is None else branch,'date':'2037-02-03',
            'action':'CLOSE','counted_cash':'75','counted_card':'0','counted_other':'0','notes':'CODEX UAT'}
    values.update(changes)
    cl=c.m.app.test_client()
    return cl.get('/accounting/daily-closing',query_string=values) if method=='get' else cl.post('/accounting/daily-closing',data=values)


def receipt(c,amount=100,method='CASH',when=datetime(2037,2,3,10)):
    row=c.m.Payment(order_id=c.order.id,amount=amount,method=method,created_at=when)
    c.m.db.session.add(row);c.m.db.session.flush();return row


def refund(c,p,amount=25,when=datetime(2037,2,3,11)):
    row=c.m.PaymentRefund(payment_id=p.id,order_id=c.order.id,amount=amount,
        reason='CODEX UAT',created_by=c.user.id,created_at=when)
    c.m.db.session.add(row);c.m.db.session.flush();return row


@pytest.mark.parametrize('code',['TECHNICIAN','NURSING','RADIOLOGIST','CASE_COORDINATOR','CONTRACTS'])
@pytest.mark.parametrize('method',['get','post'])
def test_order_view_does_not_authorize_cash_closing(closing_case,code,method):
    c=closing_case;role(c,code)
    assert request(c,method).status_code==403
    assert c.m.DailyClosing.query.filter_by(branch_id=c.a.id).count()==0


@pytest.mark.parametrize('method',['get','post'])
@pytest.mark.parametrize('boundary',['other_branch','unscoped','inactive'])
def test_cashier_branch_and_active_boundaries(closing_case,method,boundary):
    c=closing_case;branch=c.b.id if boundary=='other_branch' else c.a.id
    if boundary=='unscoped':c.user.branch_id=None
    if boundary=='inactive':c.user.active=False
    response=request(c,method,branch=branch)
    assert response.status_code in ((302,403) if boundary=='inactive' else (403,))
    assert c.m.DailyClosing.query.filter_by(branch_id=c.a.id).count()==0


def test_management_reads_own_branch_but_cannot_close(closing_case):
    c=closing_case;role(c,'MANAGEMENT')
    assert request(c).status_code==200 and not c.context['can_edit']
    assert [b.id for b in c.context['branches']]==[c.a.id]
    assert request(c,'post').status_code==403
    assert request(c,branch=c.b.id).status_code==403


def test_reception_collection_setting_controls_closing(closing_case):
    c=closing_case;role(c,'RECEPTION')
    assert request(c).status_code==200 and c.context['can_edit']
    c.a.reception_collection_enabled=False;c.m.db.session.flush()
    assert request(c,'post').status_code==403


def test_save_close_and_closed_snapshot_cannot_be_overwritten(closing_case):
    c=closing_case;p=receipt(c);refund(c,p)
    assert request(c,'post',action='SAVE').status_code==302
    row=c.m.DailyClosing.query.filter_by(branch_id=c.a.id).one()
    assert row.status=='OPEN' and row.expected_cash==75 and row.difference==0
    assert request(c,'post').status_code==302
    assert row.status=='CLOSED' and row.closed_by==c.user.id and row.closed_at
    snapshot=(row.expected_cash,row.counted_cash,row.notes,row.closed_at)
    before=c.m.AuditLog.query.filter_by(entity='daily_closing',entity_id=str(row.id)).count()
    receipt(c,50)
    assert request(c,'post',action='SAVE',counted_cash='999',notes='overwrite').status_code==302
    assert request(c,'post',action='CLOSE',counted_cash='999').status_code==302
    assert snapshot==(row.expected_cash,row.counted_cash,row.notes,row.closed_at)
    assert c.m.AuditLog.query.filter_by(entity='daily_closing',entity_id=str(row.id)).count()==before==2
    assert request(c).status_code==200
    assert c.context['totals']['CASH']==75 and c.context['closed'] and not c.context['can_edit']


def test_global_admin_can_select_branch_but_cannot_overwrite_closed_day(closing_case):
    c=closing_case;role(c,'SUPER_ADMIN');c.user.branch_id=None
    assert request(c,'post',branch=c.b.id).status_code==302
    row=c.m.DailyClosing.query.filter_by(branch_id=c.b.id).one()
    assert row.status=='CLOSED'
    assert request(c,'post',branch=c.b.id,counted_cash='999').status_code==302
    assert row.counted_cash==75


@pytest.mark.parametrize('value',['nan','inf','-inf','not-money'])
def test_non_finite_or_invalid_counts_do_not_create_closing(closing_case,value):
    c=closing_case
    assert request(c,'post',counted_cash=value).status_code==302
    assert c.m.DailyClosing.query.filter_by(branch_id=c.a.id).count()==0


@pytest.mark.parametrize('field,value',[('date','bad-date'),('action','REOPEN')])
def test_invalid_date_or_action_is_rejected(closing_case,field,value):
    c=closing_case
    assert request(c,'post',**{field:value}).status_code==400
    assert c.m.DailyClosing.query.filter_by(branch_id=c.a.id).count()==0


def test_refunds_belong_to_refund_date_and_original_payment_bucket(closing_case):
    c=closing_case
    cash=receipt(c,100,when=datetime(2037,2,2,10));refund(c,cash,25)
    card=receipt(c,200,'CARD');refund(c,card,40)
    other=receipt(c,30,'TRANSFER');refund(c,other,5,datetime(2037,2,4,0))
    assert c.m.daily_payment_totals(c.a.id,date(2037,2,2))=={'CASH':100,'CARD':0,'OTHER':0}
    assert c.m.daily_payment_totals(c.a.id,date(2037,2,3))=={'CASH':-25,'CARD':160,'OTHER':30}
    assert c.m.daily_payment_totals(c.a.id,date(2037,2,4))=={'CASH':0,'CARD':0,'OTHER':-5}
    assert c.m.daily_payment_totals(c.b.id,date(2037,2,3))=={'CASH':0,'CARD':0,'OTHER':0}


def test_decimal_totals_and_accounting_failure_are_not_silently_zeroed(closing_case,monkeypatch):
    c=closing_case;receipt(c,0.1);receipt(c,0.2)
    assert c.m.daily_payment_totals(c.a.id,date(2037,2,3))['CASH']==0.3
    def broken_query(*a,**kw):raise RuntimeError('CODEX UAT accounting unavailable')
    monkeypatch.setattr(type(c.m.Payment.query),'all',broken_query)
    with pytest.raises(RuntimeError):c.m.daily_payment_totals(c.a.id,date(2037,2,3))


@pytest.mark.parametrize('language',['ar','en'])
@pytest.mark.parametrize('closed',[False,True])
def test_bilingual_template_disables_closed_day_controls(closing_case,language,closed):
    from jinja2 import Environment,ChoiceLoader,DictLoader,FileSystemLoader
    c=closing_case
    assert request(c).status_code==200
    context=dict(c.context,ui_lang=language,closed=closed,can_edit=not closed)
    if closed:context['row']=SimpleNamespace(counted_cash=75,counted_card=0,counted_other=0,
        difference=0,notes='CODEX UAT',closed_at=datetime(2037,2,3,20))
    env=Environment(loader=ChoiceLoader([DictLoader({'base.html':'{% block page_title %}{% endblock %}{% block content %}{% endblock %}'}),FileSystemLoader('templates')]),autoescape=True)
    html=env.get_template('daily_closing.html').render(**context)
    assert ('التقفيل اليومي' if language=='ar' else 'Daily Cashier Closing') in html
    if closed:
        assert 'fieldset disabled' in html and 'value="CLOSE"' not in html
        assert ('اليوم مُقفل' if language=='ar' else 'Day closed') in html
    else:assert 'value="CLOSE"' in html

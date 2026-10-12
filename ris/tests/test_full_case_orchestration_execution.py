from web.source_contract import get_source as _get_source
from werkzeug.security import generate_password_hash


def _user(m, username='full-case-exec-admin', super_admin=True):
    code='SUPER_ADMIN' if super_admin else 'RIS_OPERATOR'
    role=m.Role.query.filter_by(code=code).first()
    if role is None:
        role=m.Role(code=code,name=code,permissions_json='["data.cancel.case"]')
        m.db.session.add(role)
        m.db.session.flush()
    user=m.User.query.filter_by(username=username).first()
    if user is None:
        user=m.User(
            username=username,
            full_name=username,
            password_hash=generate_password_hash('secret'),
            role_id=role.id,
            active=True,
        )
        m.db.session.add(user)
        m.db.session.commit()
    return user


def _login(client,user):
    with client.session_transaction() as session:
        session['uid']=user.id


def _case(m,suffix,status='CANCELLED'):
    patient=m.Patient(patient_id=f'FULL-EXEC-P-{suffix}',name=f'Full Exec {suffix}')
    m.db.session.add(patient)
    m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,
        accession=f'FULL-EXEC-A-{suffix}',
        modality='DX',
        procedure='Full Case Execution',
        scheduled=m.datetime.utcnow(),
        status=status,
        pacs_status='WAITING',
        pacs_image_count=0,
        pacs_study_id='',
    )
    m.db.session.add(order)
    m.db.session.commit()
    return patient,order


def _plan(pacs='NOT_REQUIRED',reports='COMPLETE',ris='READY'):
    return {
        'full_case_orchestration':{
            'can_execute_full_case':True,
            'blockers':[],
            'stages':[
                {'code':'PACS_IMAGES_ONLY','state':pacs},
                {'code':'REPORTS_ONLY','state':reports},
                {'code':'RIS_CASE_DATA_ONLY','state':ris},
            ],
        }
    }


def _post(client,order,reason='Synthetic full case execution'):
    return client.post(
        f'/admin/cancellation-center/order/{order.id}/delete-full-case',
        data={'confirm_accession':order.accession,'reason':reason},
    )


def test_full_case_execution_disabled_by_default(app_ctx,monkeypatch):
    m=app_ctx
    admin=_user(m)
    patient,order=_case(m,'DISABLED')
    monkeypatch.delenv('RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED',raising=False)
    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==409
    payload=response.get_json()
    assert payload['error']=='FULL_CASE_EXECUTION_DISABLED'
    assert m.db.session.get(m.Order,order.id) is not None


def test_full_case_execution_requires_super_admin(app_ctx,monkeypatch):
    m=app_ctx
    user=_user(m,'full-case-exec-operator',False)
    patient,order=_case(m,'ROLE')
    monkeypatch.setenv('RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED','1')
    client=m.app.test_client(); _login(client,user)
    response=_post(client,order)
    assert response.status_code==403


def test_full_case_execution_requires_cancelled_exact_accession_and_reason(app_ctx,monkeypatch):
    m=app_ctx
    admin=_user(m)
    monkeypatch.setenv('RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED','1')
    client=m.app.test_client(); _login(client,admin)

    patient,active=_case(m,'ACTIVE',status='COMPLETED')
    response=_post(client,active)
    assert response.status_code==409
    assert response.get_json()['error']=='ORDER_NOT_CANCELLED'

    patient,order=_case(m,'CONFIRM')
    response=client.post(
        f'/admin/cancellation-center/order/{order.id}/delete-full-case',
        data={'confirm_accession':'WRONG','reason':'Valid reason'},
    )
    assert response.status_code==409
    assert response.get_json()['error']=='ACCESSION_CONFIRMATION_MISMATCH'

    response=client.post(
        f'/admin/cancellation-center/order/{order.id}/delete-full-case',
        data={'confirm_accession':order.accession,'reason':'x'},
    )
    assert response.status_code==400
    assert response.get_json()['error']=='REASON_REQUIRED'


def test_full_case_execution_stops_after_pacs_failure(app_ctx,monkeypatch):
    m=app_ctx
    admin=_user(m)
    patient,order=_case(m,'PACSFAIL')
    monkeypatch.setenv('RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED','1')
    monkeypatch.setattr(m,'granular_delete_order_preview_snapshot',lambda row:_plan('READY','READY','READY_AFTER_REPORTS'))
    calls=[]
    def pacs(*args,**kwargs):
        calls.append('PACS')
        return {'ok':False,'deleted':True,'error':'ORTHANC_DELETE_FAILED'},502
    def reports(*args,**kwargs):
        calls.append('REPORTS')
        return {'ok':True},200
    def ris(*args,**kwargs):
        calls.append('RIS')
        return {'ok':True},200
    monkeypatch.setattr(m,'granular_delete_images_only_execute',pacs)
    monkeypatch.setattr(m,'granular_delete_reports_only_execute',reports)
    monkeypatch.setattr(m,'granular_delete_ris_case_only_execute',ris)
    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==502
    assert response.get_json()['failed_stage']=='PACS_IMAGES_ONLY'
    assert response.get_json()['partial_destructive_changes'] is True
    assert calls==['PACS']


def test_full_case_execution_stops_after_reports_failure(app_ctx,monkeypatch):
    m=app_ctx
    admin=_user(m)
    patient,order=_case(m,'REPORTFAIL')
    # Ensure stage 2 is not skipped by the executor's fresh report_count query.
    report=m.Report(order_id=order.id,status='DRAFT')
    m.db.session.add(report); m.db.session.commit()
    monkeypatch.setenv('RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED','1')
    monkeypatch.setattr(m,'granular_delete_order_preview_snapshot',lambda row:_plan('READY','READY','READY_AFTER_REPORTS'))
    calls=[]
    def pacs(*args,**kwargs):
        calls.append('PACS')
        return {'ok':True},200
    def reports(*args,**kwargs):
        calls.append('REPORTS')
        return {'ok':False,'error':'REPORTS_ONLY_PREFLIGHT_BLOCKED'},409
    def ris(*args,**kwargs):
        calls.append('RIS')
        return {'ok':True},200
    monkeypatch.setattr(m,'granular_delete_images_only_execute',pacs)
    monkeypatch.setattr(m,'granular_delete_reports_only_execute',reports)
    monkeypatch.setattr(m,'granular_delete_ris_case_only_execute',ris)
    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==409
    payload=response.get_json()
    assert payload['failed_stage']=='REPORTS_ONLY'
    assert calls==['PACS','REPORTS']
    assert 'PACS_IMAGES_ONLY' in payload['completed_stages']


def test_full_case_execution_runs_required_sequence_and_final_postcheck(app_ctx,monkeypatch):
    m=app_ctx
    admin=_user(m)
    patient,order=_case(m,'SUCCESS')
    report=m.Report(order_id=order.id,status='DRAFT')
    m.db.session.add(report); m.db.session.commit()
    monkeypatch.setenv('RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED','1')
    monkeypatch.setattr(m,'granular_delete_order_preview_snapshot',lambda row:_plan('READY','READY','READY_AFTER_REPORTS'))
    calls=[]
    def pacs(*args,**kwargs):
        calls.append('PACS')
        return {'ok':True,'deleted':True},200
    def reports(*args,**kwargs):
        calls.append('REPORTS')
        # Model the contract expected after a successful report executor.
        m.Report.query.filter_by(order_id=order.id).delete(synchronize_session=False)
        m.db.session.commit()
        return {'ok':True,'deleted':True},200
    def ris(*args,**kwargs):
        calls.append('RIS')
        return {'ok':True,'deleted':True},200
    monkeypatch.setattr(m,'granular_delete_images_only_execute',pacs)
    monkeypatch.setattr(m,'granular_delete_reports_only_execute',reports)
    monkeypatch.setattr(m,'granular_delete_ris_case_only_execute',ris)
    monkeypatch.setattr(
        m,'_full_case_orchestration_final_postcheck',
        lambda order_id,patient_id:{
            'ok':True,'order_removed':True,'patient_preserved':True,
            'report_count':0,'direct_dependency_count':0,'dependency_rows':[],
        },
    )
    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==200
    payload=response.get_json()
    assert payload['ok'] is True
    assert payload['full_case_deleted'] is True
    assert calls==['PACS','REPORTS','RIS']
    assert payload['completed_stages']==['PACS_IMAGES_ONLY','REPORTS_ONLY','RIS_CASE_DATA_ONLY']


def test_full_case_execution_skips_completed_pacs_and_reports(app_ctx,monkeypatch):
    m=app_ctx
    admin=_user(m)
    patient,order=_case(m,'SKIP')
    monkeypatch.setenv('RADBRIDGE_FULL_CASE_ORCHESTRATION_EXECUTION_ENABLED','1')
    monkeypatch.setattr(m,'granular_delete_order_preview_snapshot',lambda row:_plan('COMPLETE','COMPLETE','READY'))
    calls=[]
    monkeypatch.setattr(m,'granular_delete_images_only_execute',lambda *a,**k: (_ for _ in ()).throw(AssertionError('PACS should be skipped')))
    monkeypatch.setattr(m,'granular_delete_reports_only_execute',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Reports should be skipped')))
    def ris(*args,**kwargs):
        calls.append('RIS')
        return {'ok':True,'deleted':True},200
    monkeypatch.setattr(m,'granular_delete_ris_case_only_execute',ris)
    monkeypatch.setattr(
        m,'_full_case_orchestration_final_postcheck',
        lambda order_id,patient_id:{'ok':True,'order_removed':True,'patient_preserved':True,'report_count':0,'direct_dependency_count':0,'dependency_rows':[]},
    )
    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==200
    payload=response.get_json()
    assert calls==['RIS']
    assert payload['completed_stages'][0]=='PACS_IMAGES_ONLY_SKIPPED_COMPLETE'
    assert payload['completed_stages'][1]=='REPORTS_ONLY_SKIPPED_COMPLETE'


def test_full_case_executor_contains_no_new_direct_destructive_implementation(app_ctx):
    import inspect
    m=app_ctx
    source=_get_source(m.granular_delete_full_case_orchestration_execute)
    assert 'requests.delete' not in source
    assert 'os.remove' not in source
    assert '.unlink(' not in source
    assert 'shutil.rmtree' not in source
    assert 'db.session.delete' not in source
    assert 'granular_delete_images_only_execute' in source
    assert 'granular_delete_reports_only_execute' in source
    assert 'granular_delete_ris_case_only_execute' in source

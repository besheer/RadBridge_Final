from web.source_contract import get_source as _get_source
from datetime import timedelta
from pathlib import Path

from sqlalchemy import text
from werkzeug.security import generate_password_hash


def _user(m, username='reports-delete-admin', super_admin=True):
    code='SUPER_ADMIN' if super_admin else 'REPORT_OPERATOR'
    role=m.Role.query.filter_by(code=code).first()
    if role is None:
        role=m.Role(
            code=code,
            name=code.replace('_',' ').title(),
            permissions_json='["data.cancel.case"]',
        )
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


def _lease_table(m):
    m.db.session.execute(text('''
        CREATE TABLE IF NOT EXISTS report_edit_lease (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL UNIQUE,
            report_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            editor_type VARCHAR(32) NOT NULL,
            lease_token_hash VARCHAR(80) NOT NULL,
            acquired_at DATETIME NOT NULL,
            renewed_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL
        )
    '''))
    m.db.session.commit()


def _case(m,tmp_path,suffix, *, pacs_status='AVAILABLE'):
    import report_storage_safety as storage

    m.REPORT_DIR=str(tmp_path/'report-files')
    patient=m.Patient(
        patient_id=f'RPT-EXEC-P-{suffix}',
        name=f'Report Execute {suffix}',
    )
    m.db.session.add(patient)
    m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,
        accession=f'RPT-EXEC-A-{suffix}',
        modality='DX',
        procedure='Report Execution Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
        pacs_status=pacs_status,
        pacs_image_count=7,
        pacs_study_id=f'ORTHANC-{suffix}',
    )
    m.db.session.add(order)
    m.db.session.flush()
    report=m.Report(
        order_id=order.id,
        status='DRAFT',
        findings='findings',
        impression='impression',
    )
    m.db.session.add(report)
    m.db.session.flush()

    path=storage.version_artifact_path(
        m.REPORT_DIR,patient,order,1,'docx'
    )
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'delete-reports-only-test')
    report.source_path=str(path)
    report.docx_path=str(path)

    version=m.ReportVersion(
        report_id=report.id,
        accession=order.accession,
        version_no=1,
        action='DRAFT',
        status='DRAFT',
        editor_type='ONLYOFFICE',
        source_type='DOCX',
        source_path=str(path),
        docx_path=str(path),
    )
    m.db.session.add(version)
    m.db.session.commit()
    return patient,order,report,version,path


def _post(client,order, accession=None, reason='Duplicate report cleanup'):
    return client.post(
        f'/admin/cancellation-center/order/{order.id}/delete-reports',
        data={
            'confirm_accession': accession if accession is not None else order.accession,
            'reason': reason,
        },
    )


def test_delete_reports_only_requires_super_admin(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    user=_user(m,'reports-delete-operator',False)
    patient,order,report,version,path=_case(m,tmp_path,'ROLE')
    client=m.app.test_client(); _login(client,user)

    response=_post(client,order)
    assert response.status_code==403
    assert m.Report.query.get(report.id) is not None
    assert m.ReportVersion.query.get(version.id) is not None
    assert path.exists()


def test_delete_reports_only_requires_exact_accession_and_reason(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    admin=_user(m)
    patient,order,report,version,path=_case(m,tmp_path,'CONFIRM')
    client=m.app.test_client(); _login(client,admin)

    mismatch=_post(client,order,accession='WRONG')
    assert mismatch.status_code==409
    assert mismatch.get_json()['error']=='ACCESSION_CONFIRMATION_MISMATCH'

    short=_post(client,order,reason='bad')
    assert short.status_code==400
    assert short.get_json()['error']=='REASON_REQUIRED'

    assert m.Report.query.get(report.id) is not None
    assert m.ReportVersion.query.get(version.id) is not None
    assert path.exists()


def test_delete_reports_only_blocks_coordinator_task(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    admin=_user(m)
    patient,order,report,version,path=_case(m,tmp_path,'COORD')
    m.db.session.add(m.CoordinatorTask(
        order_id=order.id,
        report_id=report.id,
        status='PENDING_FORMATTING',
    ))
    m.db.session.commit()
    client=m.app.test_client(); _login(client,admin)

    response=_post(client,order)
    assert response.status_code==409
    assert 'COORDINATOR_TASK_PRESENT' in response.get_json()['blockers']
    assert m.CoordinatorTask.query.filter_by(report_id=report.id).count()==1
    assert m.Report.query.get(report.id) is not None
    assert path.exists()


def test_delete_reports_only_blocks_active_lease(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    admin=_user(m)
    patient,order,report,version,path=_case(m,tmp_path,'ACTIVELEASE')
    now=m.datetime.utcnow()
    m.db.session.execute(text('''
        INSERT INTO report_edit_lease (
            order_id,report_id,user_id,editor_type,lease_token_hash,
            acquired_at,renewed_at,expires_at
        ) VALUES (
            :order_id,:report_id,:user_id,'ONLYOFFICE','hash',
            :now,:now,:expires
        )
    '''),{
        'order_id':order.id,'report_id':report.id,'user_id':admin.id,
        'now':now,'expires':now+timedelta(minutes=5),
    })
    m.db.session.commit()
    client=m.app.test_client(); _login(client,admin)

    response=_post(client,order)
    assert response.status_code==409
    assert 'ACTIVE_REPORT_EDIT_LEASE' in response.get_json()['blockers']
    assert m.Report.query.get(report.id) is not None
    assert path.exists()


def test_delete_reports_only_success_quarantines_files_and_preserves_case(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    admin=_user(m)
    patient,order,report,version,path=_case(m,tmp_path,'SUCCESS')
    patient_id=patient.id; order_id=order.id; report_id=report.id
    accession=order.accession
    pacs_before=(order.pacs_study_id,order.pacs_image_count,order.pacs_status)

    # Expired lease is cleanup-owned by execution, not a blocker.
    now=m.datetime.utcnow()
    m.db.session.execute(text('''
        INSERT INTO report_edit_lease (
            order_id,report_id,user_id,editor_type,lease_token_hash,
            acquired_at,renewed_at,expires_at
        ) VALUES (
            :order_id,:report_id,:user_id,'ONLYOFFICE','expired-hash',
            :now,:now,:expires
        )
    '''),{
        'order_id':order.id,'report_id':report.id,'user_id':admin.id,
        'now':now-timedelta(minutes=10),'expires':now-timedelta(minutes=5),
    })
    m.db.session.commit()

    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==200
    body=response.get_json()
    assert body['ok'] is True
    assert body['deleted'] is True
    assert body['report_count_deleted']==1
    assert body['version_count_deleted']==1
    assert body['quarantined'] is True

    assert m.Report.query.filter_by(id=report_id).count()==0
    assert m.ReportVersion.query.filter_by(report_id=report_id).count()==0
    assert m.Order.query.filter_by(id=order_id).count()==1
    assert m.Patient.query.filter_by(id=patient_id).count()==1
    preserved=m.db.session.get(m.Order,order_id)
    assert (preserved.pacs_study_id,preserved.pacs_image_count,preserved.pacs_status)==pacs_before
    assert m.db.session.execute(text(
        'SELECT COUNT(*) FROM report_edit_lease WHERE order_id=:order_id'
    ),{'order_id':order_id}).scalar()==0

    assert not path.exists()
    quarantine=Path(body['quarantine_path'])
    assert quarantine.exists()
    assert (quarantine/'versions'/'v001'/'report.docx').read_bytes()==b'delete-reports-only-test'

    audit=m.AuditLog.query.filter_by(
        action='REPORTS_ONLY_DELETED_ADMIN',entity='order',entity_id=str(order_id)
    ).order_by(m.AuditLog.id.desc()).first()
    assert audit is not None
    assert accession in audit.details


def test_delete_reports_only_filesystem_failure_keeps_db_and_file(app_ctx,tmp_path,monkeypatch):
    m=app_ctx
    _lease_table(m)
    admin=_user(m)
    patient,order,report,version,path=_case(m,tmp_path,'MOVEFAIL')
    client=m.app.test_client(); _login(client,admin)

    real_replace=m.os.replace
    calls=[]
    def fail_first(src,dst):
        calls.append((src,dst))
        if len(calls)==1:
            raise OSError('simulated quarantine failure')
        return real_replace(src,dst)
    monkeypatch.setattr(m.os,'replace',fail_first)

    response=_post(client,order)
    assert response.status_code==500
    assert response.get_json()['deleted'] is False
    assert m.Report.query.get(report.id) is not None
    assert m.ReportVersion.query.get(version.id) is not None
    assert path.exists()


def test_delete_reports_only_second_execution_hard_blocks(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    admin=_user(m)
    patient,order,report,version,path=_case(m,tmp_path,'SECOND')
    client=m.app.test_client(); _login(client,admin)

    first=_post(client,order)
    assert first.status_code==200
    second=_post(client,order)
    assert second.status_code==409
    body=second.get_json()
    assert body['deleted'] is False
    assert 'NO_REPORT' in body['blockers']


def test_delete_reports_only_route_does_not_reference_pacs_delete(app_ctx):
    import inspect
    m=app_ctx
    source=_get_source(m.granular_delete_reports_only_execute)
    assert 'requests.delete' not in source
    assert 'PACS_ORTHANC_URL' not in source
    assert 'CoordinatorTask.query.delete' not in source

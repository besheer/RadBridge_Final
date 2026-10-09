from datetime import timedelta
from pathlib import Path

from sqlalchemy import text
from werkzeug.security import generate_password_hash


def _admin(m):
    role=m.Role.query.filter_by(code='SUPER_ADMIN').first()
    if role is None:
        role=m.Role(code='SUPER_ADMIN',name='Super Admin')
        m.db.session.add(role)
        m.db.session.flush()
    user=m.User.query.filter_by(username='reports-preview-admin').first()
    if user is None:
        user=m.User(
            username='reports-preview-admin',
            full_name='Reports Preview Admin',
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


def _case(m,suffix):
    patient=m.Patient(
        patient_id=f'RPT-DEL-P-{suffix}',
        name=f'Report Delete Preview {suffix}',
    )
    m.db.session.add(patient)
    m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,
        accession=f'RPT-DEL-A-{suffix}',
        modality='DX',
        procedure='Report Preview Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )
    m.db.session.add(order)
    m.db.session.flush()
    report=m.Report(
        order_id=order.id,
        status='DRAFT',
        findings='preview',
        impression='preview',
    )
    m.db.session.add(report)
    m.db.session.flush()
    m.db.session.commit()
    return patient,order,report


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


def _canonical_artifact(m,tmp_path,patient,order,version_no=1):
    import report_storage_safety as storage
    m.REPORT_DIR=str(tmp_path/'report-files')
    path=storage.version_artifact_path(
        m.REPORT_DIR,patient,order,version_no,'docx'
    )
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'report-preview-test')
    return path


def _add_version(m,report,order,path,version_no=1):
    row=m.ReportVersion(
        report_id=report.id,
        accession=order.accession,
        version_no=version_no,
        action='DRAFT',
        status='DRAFT',
        editor_type='ONLYOFFICE',
        source_type='DOCX',
        source_path=str(path),
        docx_path=str(path),
    )
    m.db.session.add(row)
    m.db.session.commit()
    return row


def test_reports_only_preview_clean_case_is_ready(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    patient,order,report=_case(m,'CLEAN')
    path=_canonical_artifact(m,tmp_path,patient,order)
    _add_version(m,report,order,path)

    payload=m.granular_delete_order_preview_snapshot(order)
    preview=payload['reports_only']

    assert payload['readonly'] is True
    assert preview['readonly'] is True
    assert preview['report_count']==1
    assert preview['version_count']==1
    assert preview['coordinator_task_count']==0
    assert preview['lease']['active_count']==0
    assert preview['storage']['artifact_count']==1
    assert preview['storage']['unsafe_path_count']==0
    assert preview['can_delete_reports_only'] is True
    assert preview['blocker_codes']==[]


def test_reports_only_preview_blocks_coordinator_task(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    patient,order,report=_case(m,'COORD')
    path=_canonical_artifact(m,tmp_path,patient,order)
    _add_version(m,report,order,path)
    m.db.session.add(m.CoordinatorTask(
        order_id=order.id,
        report_id=report.id,
        status='PENDING_FORMATTING',
    ))
    m.db.session.commit()

    preview=m.granular_delete_order_preview_snapshot(order)['reports_only']
    assert preview['coordinator_task_count']==1
    assert 'COORDINATOR_TASK_PRESENT' in preview['blocker_codes']
    assert preview['can_delete_reports_only'] is False


def test_reports_only_preview_blocks_active_edit_lease(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    admin=_admin(m)
    patient,order,report=_case(m,'LEASE')
    path=_canonical_artifact(m,tmp_path,patient,order)
    _add_version(m,report,order,path)
    now=m.datetime.utcnow()
    m.db.session.execute(text('''
        INSERT INTO report_edit_lease (
            order_id,report_id,user_id,editor_type,lease_token_hash,
            acquired_at,renewed_at,expires_at
        ) VALUES (
            :order_id,:report_id,:user_id,'ONLYOFFICE','test-hash',
            :now,:now,:expires
        )
    '''),{
        'order_id':order.id,
        'report_id':report.id,
        'user_id':admin.id,
        'now':now,
        'expires':now+timedelta(minutes=10),
    })
    m.db.session.commit()

    preview=m.granular_delete_order_preview_snapshot(order)['reports_only']
    assert preview['lease']['active_count']==1
    assert 'ACTIVE_REPORT_EDIT_LEASE' in preview['blocker_codes']
    assert preview['can_delete_reports_only'] is False


def test_reports_only_preview_blocks_artifact_outside_case_root(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    patient,order,report=_case(m,'OUTSIDE')
    m.REPORT_DIR=str(tmp_path/'report-files')
    outside=tmp_path/'outside-report.docx'
    outside.write_bytes(b'outside')
    _add_version(m,report,order,outside)

    preview=m.granular_delete_order_preview_snapshot(order)['reports_only']
    assert preview['storage']['unsafe_path_count']==1
    assert 'REPORT_ARTIFACT_OUTSIDE_CASE_ROOT' in preview['blocker_codes']
    assert preview['can_delete_reports_only'] is False


def test_reports_only_preview_blocks_version_accession_mismatch(app_ctx,tmp_path):
    m=app_ctx
    _lease_table(m)
    patient,order,report=_case(m,'MISMATCH')
    path=_canonical_artifact(m,tmp_path,patient,order)
    version=_add_version(m,report,order,path)
    version.accession='WRONG-ACCESSION'
    m.db.session.commit()

    preview=m.granular_delete_order_preview_snapshot(order)['reports_only']
    assert 'REPORT_VERSION_ACCESSION_MISMATCH' in preview['blocker_codes']
    assert preview['can_delete_reports_only'] is False


def test_reports_only_preview_route_and_helper_are_read_only(app_ctx,tmp_path):
    import inspect

    m=app_ctx
    _lease_table(m)
    admin=_admin(m)
    patient,order,report=_case(m,'RO')
    path=_canonical_artifact(m,tmp_path,patient,order)
    _add_version(m,report,order,path)

    before=(
        m.Report.query.count(),
        m.ReportVersion.query.count(),
        m.CoordinatorTask.query.count(),
        m.Order.query.count(),
        m.Patient.query.count(),
        m.AuditLog.query.count(),
        path.read_bytes(),
    )

    client=m.app.test_client()
    _login(client,admin)
    response=client.get(
        f'/admin/cancellation-center/order/{order.id}/preview?format=json'
    )
    assert response.status_code==200
    payload=response.get_json()
    assert payload['reports_only']['readonly'] is True
    assert 'can_delete_reports_only' in payload['reports_only']

    after=(
        m.Report.query.count(),
        m.ReportVersion.query.count(),
        m.CoordinatorTask.query.count(),
        m.Order.query.count(),
        m.Patient.query.count(),
        m.AuditLog.query.count(),
        path.read_bytes(),
    )
    assert after==before

    source=inspect.getsource(m.granular_delete_reports_only_preview_snapshot)
    for forbidden in (
        'db.session.delete',
        'requests.delete',
        'os.remove',
        '.unlink(',
        'shutil.rmtree',
    ):
        assert forbidden not in source

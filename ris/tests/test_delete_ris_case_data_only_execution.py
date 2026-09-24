from werkzeug.security import generate_password_hash


def _user(m, username='ris-case-delete-admin', super_admin=True):
    code='SUPER_ADMIN' if super_admin else 'RIS_OPERATOR'
    role=m.Role.query.filter_by(code=code).first()
    if role is None:
        role=m.Role(code=code,name=code,permissions_json='["data.cancel.case"]')
        m.db.session.add(role); m.db.session.flush()
    user=m.User.query.filter_by(username=username).first()
    if user is None:
        user=m.User(username=username,full_name=username,password_hash=generate_password_hash('secret'),role_id=role.id,active=True)
        m.db.session.add(user); m.db.session.commit()
    return user


def _login(client,user):
    with client.session_transaction() as session:
        session['uid']=user.id


def _case(m,suffix,status='CANCELLED'):
    patient=m.Patient(patient_id=f'RIS-EXEC-P-{suffix}',name=f'RIS Executor {suffix}')
    m.db.session.add(patient); m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,accession=f'RIS-EXEC-A-{suffix}',modality='DX',
        procedure='RIS Executor Exam',scheduled=m.datetime.utcnow(),status=status,
        pacs_status='AVAILABLE',pacs_image_count=5,pacs_study_id=f'ORTHANC-{suffix}',
    )
    m.db.session.add(order); m.db.session.commit()
    return patient,order


def _post(client,order,accession=None,reason='Administrative duplicate case cleanup'):
    return client.post(
        f'/admin/cancellation-center/order/{order.id}/delete-ris-case-data',
        data={'confirm_accession':accession if accession is not None else order.accession,'reason':reason},
    )


def test_ris_case_delete_requires_super_admin(app_ctx):
    m=app_ctx; user=_user(m,'ris-case-operator',False); patient,order=_case(m,'ROLE')
    client=m.app.test_client(); _login(client,user)
    response=_post(client,order)
    assert response.status_code==403
    assert m.db.session.get(m.Order,order.id) is not None
    assert m.db.session.get(m.Patient,patient.id) is not None


def test_ris_case_delete_requires_exact_accession_and_reason(app_ctx):
    m=app_ctx; admin=_user(m); patient,order=_case(m,'CONFIRM')
    client=m.app.test_client(); _login(client,admin)
    assert _post(client,order,accession='WRONG').status_code==409
    assert _post(client,order,reason='bad').status_code==400
    assert m.db.session.get(m.Order,order.id) is not None


def test_ris_case_delete_blocks_non_cancelled_order(app_ctx):
    m=app_ctx; admin=_user(m); patient,order=_case(m,'ACTIVE',status='COMPLETED')
    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==409
    assert 'ORDER_NOT_CANCELLED' in response.get_json()['blockers']
    assert m.db.session.get(m.Order,order.id) is not None


def test_ris_case_delete_blocks_reports_first(app_ctx):
    m=app_ctx; admin=_user(m); patient,order=_case(m,'REPORT')
    report=m.Report(order_id=order.id,status='DRAFT',findings='',impression='')
    m.db.session.add(report); m.db.session.commit()
    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==409
    assert any('DELETE_REPORTS_FIRST' in x for x in response.get_json()['blockers'])
    assert m.db.session.get(m.Order,order.id) is not None
    assert m.db.session.get(m.Report,report.id) is not None


def test_ris_case_delete_success_preserves_patient_pacs_attachment_and_audit(app_ctx):
    m=app_ctx; admin=_user(m); patient,order=_case(m,'SUCCESS')
    order_id=order.id; patient_id=patient.id; accession=order.accession
    pacs=(order.pacs_study_id,order.pacs_image_count,order.pacs_status)
    attachment=m.Attachment(
        patient_id=patient.id,order_id=order.id,category='OTHER',
        original_name='keep.txt',stored_path='/tmp/keep.txt',mime_type='text/plain',
    )
    note=m.ClinicalNote(order_id=order.id,note_type='GENERAL',text='case-owned note')
    m.db.session.add_all([attachment,note]); m.db.session.commit()
    attachment_id=attachment.id; note_id=note.id

    client=m.app.test_client(); _login(client,admin)
    response=_post(client,order)
    assert response.status_code==200
    body=response.get_json(); assert body['ok'] is True and body['deleted'] is True
    assert body['patient_preserved'] is True and body['pacs_images_preserved'] is True
    assert m.db.session.get(m.Order,order_id) is None
    assert m.db.session.get(m.Patient,patient_id) is not None
    kept=m.db.session.get(m.Attachment,attachment_id)
    assert kept is not None and kept.order_id is None
    assert m.db.session.get(m.ClinicalNote,note_id) is None
    audit=m.AuditLog.query.filter_by(action='RIS_CASE_DATA_DELETED_ADMIN',entity='order',entity_id=str(order_id)).order_by(m.AuditLog.id.desc()).first()
    assert audit is not None and accession in audit.details
    assert pacs[0] in audit.details


def test_ris_case_delete_second_execution_is_not_found(app_ctx):
    m=app_ctx; admin=_user(m); patient,order=_case(m,'SECOND')
    client=m.app.test_client(); _login(client,admin)
    order_id=order.id
    first=_post(client,order); assert first.status_code==200
    second=client.post(
        f'/admin/cancellation-center/order/{order_id}/delete-ris-case-data',
        data={'confirm_accession':order.accession,'reason':'Repeat deletion attempt'},
    )
    assert second.status_code==404


def test_ris_case_delete_source_never_calls_pacs_or_filesystem_delete(app_ctx):
    import inspect
    m=app_ctx
    source=inspect.getsource(m.granular_delete_ris_case_only_execute)
    assert 'requests.delete' not in source
    assert 'PACS_ORTHANC_URL' not in source
    assert 'os.remove' not in source
    assert '.unlink(' not in source
    assert 'shutil.rmtree' not in source

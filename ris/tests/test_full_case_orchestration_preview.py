from werkzeug.security import generate_password_hash


def _user(m, username='full-case-preview-admin', super_admin=True):
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
    patient=m.Patient(patient_id=f'FULL-P-{suffix}',name=f'Full Preview {suffix}')
    m.db.session.add(patient)
    m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,
        accession=f'FULL-A-{suffix}',
        modality='DX',
        procedure='Full Case Preview',
        scheduled=m.datetime.utcnow(),
        status=status,
        pacs_status='WAITING',
        pacs_image_count=0,
        pacs_study_id='',
    )
    m.db.session.add(order)
    m.db.session.commit()
    return patient,order


def test_full_case_orchestration_clean_cancelled_case_is_preview_ready(app_ctx):
    m=app_ctx
    admin=_user(m)
    patient,order=_case(m,'READY')
    client=m.app.test_client()
    _login(client,admin)

    response=client.get(
        f'/admin/cancellation-center/order/{order.id}/preview?format=json'
    )
    assert response.status_code==200
    payload=response.get_json()['full_case_orchestration']

    assert payload['readonly'] is True
    assert payload['execution_enabled'] is False
    assert payload['patient_preserved'] is True
    assert payload['audit_append_only'] is True
    assert payload['required_sequence']==[
        'PACS_IMAGES_ONLY','REPORTS_ONLY','RIS_CASE_DATA_ONLY'
    ]
    assert [row['state'] for row in payload['stages']]==[
        'NOT_REQUIRED','COMPLETE','READY'
    ]
    assert payload['can_execute_full_case'] is True


def test_full_case_orchestration_requires_super_admin(app_ctx):
    m=app_ctx
    user=_user(m,'full-case-preview-operator',False)
    patient,order=_case(m,'ROLE')
    client=m.app.test_client()
    _login(client,user)

    response=client.get(
        f'/admin/cancellation-center/order/{order.id}/preview?format=json'
    )
    assert response.status_code==200
    payload=response.get_json()['full_case_orchestration']
    assert payload['can_execute_full_case'] is False
    assert 'SUPER_ADMIN_REQUIRED' in payload['blockers']


def test_full_case_orchestration_blocks_non_cancelled_case(app_ctx):
    m=app_ctx
    admin=_user(m)
    patient,order=_case(m,'ACTIVE',status='COMPLETED')
    client=m.app.test_client()
    _login(client,admin)

    response=client.get(
        f'/admin/cancellation-center/order/{order.id}/preview?format=json'
    )
    payload=response.get_json()['full_case_orchestration']
    assert payload['can_execute_full_case'] is False
    assert 'ORDER_NOT_CANCELLED' in payload['blockers']


def test_full_case_orchestration_preview_source_is_non_destructive(app_ctx):
    import inspect
    m=app_ctx
    source=inspect.getsource(m.granular_delete_full_case_orchestration_preview_snapshot)
    for forbidden in (
        'requests.delete',
        'db.session.delete',
        '.delete()',
        'os.remove',
        '.unlink(',
        'shutil.rmtree',
        'db.session.commit',
    ):
        assert forbidden not in source


def test_full_case_orchestration_ui_is_readonly(app_ctx):
    from pathlib import Path
    template=Path(app_ctx.app.template_folder)/'admin_cancellation_preview.html'
    source=template.read_text()
    assert 'RB_FULL_CASE_ORCHESTRATION_PREVIEW_UI_V1' in source
    assert 'preview.full_case_orchestration.execution_enabled' in source
    assert 'granular_delete_order_full_case' in source
    assert 'PACS_IMAGES_ONLY' not in source or 'Full Case Deletion' in source

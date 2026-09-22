def _make_admin(m):
    from werkzeug.security import generate_password_hash

    role=m.Role.query.filter_by(
        code='SUPER_ADMIN'
    ).first()

    if role is None:
        role=m.Role(
            code='SUPER_ADMIN',
            name='Super Admin',
        )
        m.db.session.add(role)
        m.db.session.flush()

    user=m.User(
        username='granular-preview-admin',
        full_name='Granular Preview Admin',
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


def test_granular_preview_routes_are_get_only(app_ctx):
    m=app_ctx

    rules={
        rule.rule: set(rule.methods)
        for rule in m.app.url_map.iter_rules()
    }

    paths=(
        '/admin/cancellation-center/preview',
        '/admin/cancellation-center/order/<int:order_id>/preview',
        '/admin/cancellation-center/patient/<int:patient_id>/preview',
    )

    for path in paths:
        assert path in rules
        assert 'GET' in rules[path]
        assert 'POST' not in rules[path]
        assert 'DELETE' not in rules[path]


def test_order_preview_is_readonly(app_ctx):
    m=app_ctx
    admin=_make_admin(m)

    patient=m.Patient(
        patient_id='PREVIEW-P1',
        name='Preview Test Patient',
    )

    m.db.session.add(patient)
    m.db.session.flush()

    order=m.Order(
        patient_id=patient.id,
        accession='PREVIEW-ACC-1',
        modality='DX',
        procedure='Preview Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )

    m.db.session.add(order)
    m.db.session.commit()

    before_patient=m.Patient.query.count()
    before_order=m.Order.query.count()
    before_report=m.Report.query.count()
    before_audit=m.AuditLog.query.count()

    client=m.app.test_client()
    _login(client,admin)

    response=client.get(
        f'/admin/cancellation-center/order/{order.id}/preview'
        '?format=json'
    )

    assert response.status_code==200

    payload=response.get_json()

    assert payload['readonly'] is True
    assert payload['kind']=='ORDER'
    assert payload['order']['id']==order.id
    assert payload['order']['accession']=='PREVIEW-ACC-1'
    assert payload['patient']['patient_id']=='PREVIEW-P1'

    assert m.Patient.query.count()==before_patient
    assert m.Order.query.count()==before_order
    assert m.Report.query.count()==before_report
    assert m.AuditLog.query.count()==before_audit


def test_patient_preview_is_readonly(app_ctx):
    m=app_ctx

    admin=m.User.query.filter_by(
        username='granular-preview-admin'
    ).first()

    if admin is None:
        admin=_make_admin(m)

    patient=m.Patient(
        patient_id='PREVIEW-P2',
        name='Preview Patient Two',
    )

    m.db.session.add(patient)
    m.db.session.flush()

    order=m.Order(
        patient_id=patient.id,
        accession='PREVIEW-ACC-2',
        modality='DX',
        procedure='Preview Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )

    m.db.session.add(order)
    m.db.session.commit()

    before_patient=m.Patient.query.count()
    before_order=m.Order.query.count()
    before_audit=m.AuditLog.query.count()

    client=m.app.test_client()
    _login(client,admin)

    response=client.get(
        f'/admin/cancellation-center/patient/{patient.id}/preview'
        '?format=json'
    )

    assert response.status_code==200

    payload=response.get_json()

    assert payload['readonly'] is True
    assert payload['kind']=='PATIENT'
    assert payload['patient']['patient_id']=='PREVIEW-P2'
    assert payload['summary']['order_count'] >= 1
    assert payload['safety']['full_patient_purge_allowed'] is False

    assert m.Patient.query.count()==before_patient
    assert m.Order.query.count()==before_order
    assert m.AuditLog.query.count()==before_audit


def test_preview_source_has_no_destructive_calls(app_ctx):
    import inspect

    m=app_ctx

    names=(
        'granular_delete_order_preview_snapshot',
        'granular_delete_patient_preview_snapshot',
        'granular_delete_order_preview',
        'granular_delete_patient_preview',
    )

    source='\n'.join(
        inspect.getsource(getattr(m,name))
        for name in names
    )

    forbidden=(
        'requests.delete',
        'db.session.delete',
        '.delete()',
        'os.remove',
        '.unlink(',
    )

    for marker in forbidden:
        assert marker not in source

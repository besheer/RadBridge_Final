from web.source_contract import get_source as _get_source
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
        _get_source(getattr(m,name))
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


def test_ris_case_only_preflight_is_readonly_and_unknown_dependencies_fail_closed(app_ctx):
    import inspect
    m=app_ctx

    source=_get_source(m.granular_delete_ris_case_only_preview_snapshot)
    forbidden=(
        'requests.delete',
        'db.session.delete',
        '.delete()',
        'os.remove',
        '.unlink(',
        'shutil.rmtree',
    )
    for marker in forbidden:
        assert marker not in source

    patient=m.Patient(patient_id='RIS-PREFLIGHT-P1',name='RIS Preflight Patient')
    m.db.session.add(patient)
    m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,
        accession='RIS-PREFLIGHT-ACC-1',
        modality='DX',
        procedure='RIS Preflight Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )
    m.db.session.add(order)
    m.db.session.commit()

    snap=m.granular_delete_ris_case_only_preview_snapshot(
        order,
        [{'table':'unknown_case_table','column':'order_id','count':1}],
        [],
    )
    assert snap['readonly'] is True
    assert snap['execution_implemented'] is False
    assert snap['can_prepare_execution'] is False
    assert snap['unknown_active_dependencies']==['unknown_case_table.order_id']
    assert any('UNKNOWN_DEPENDENCY' in x for x in snap['blockers'])


def test_ris_case_only_preflight_classifies_preserve_delete_and_block(app_ctx):
    m=app_ctx
    patient=m.Patient(patient_id='RIS-PREFLIGHT-P2',name='RIS Policy Patient')
    m.db.session.add(patient)
    m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,
        accession='RIS-PREFLIGHT-ACC-2',
        modality='DX',
        procedure='RIS Policy Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )
    m.db.session.add(order)
    m.db.session.commit()

    rows=[
        {'table':'appointment','column':'order_id','count':1},
        {'table':'clinical_note','column':'order_id','count':2},
        {'table':'payment','column':'order_id','count':1},
    ]
    snap=m.granular_delete_ris_case_only_preview_snapshot(order,rows,[])
    by_table={row['table']:row for row in snap['rows']}
    assert by_table['appointment']['action']=='NULLIFY_ORDER_LINK'
    assert by_table['clinical_note']['action']=='DELETE_CASE_ROW'
    assert by_table['payment']['action']=='BLOCK'
    assert snap['safe_nullify_row_count']==1
    assert snap['safe_delete_row_count']==2
    assert snap['can_prepare_execution'] is False
    assert any('FINANCIAL_HISTORY_PRESENT' in x for x in snap['blockers'])


def test_ris_case_only_preflight_blocks_reports_before_ris_delete(app_ctx):
    m=app_ctx
    patient=m.Patient(patient_id='RIS-PREFLIGHT-P3',name='RIS Report Gate Patient')
    m.db.session.add(patient)
    m.db.session.flush()
    order=m.Order(
        patient_id=patient.id,
        accession='RIS-PREFLIGHT-ACC-3',
        modality='DX',
        procedure='RIS Report Gate Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )
    m.db.session.add(order)
    m.db.session.commit()

    snap=m.granular_delete_ris_case_only_preview_snapshot(
        order,
        [{'table':'report','column':'order_id','count':1}],
        [{'id':123,'status':'DRAFT'}],
    )
    assert snap['report_count']==1
    assert snap['can_prepare_execution'] is False
    assert any('DELETE_REPORTS_FIRST' in x for x in snap['blockers'])

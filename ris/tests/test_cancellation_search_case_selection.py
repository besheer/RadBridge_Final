import app as m
from werkzeug.security import generate_password_hash


def _ensure_role(code='SUPER_ADMIN'):
    role=m.Role.query.filter_by(code=code).first()
    if role is None:
        role=m.Role(code=code,name=code)
        m.db.session.add(role)
        m.db.session.flush()
    return role


def _admin():
    role=_ensure_role()
    existing=m.User.query.filter_by(username='cancel-search-admin').first()
    if existing:
        return existing
    user=m.User(
        username='cancel-search-admin',
        full_name='Cancellation Search Admin',
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


def _case(suffix='7701'):
    patient=m.Patient(
        patient_id=f'SEL-PID-{suffix}',
        name=f'Selection Search Patient {suffix}',
        phone=f'0101234{suffix}',
    )
    m.db.session.add(patient)
    m.db.session.flush()

    order=m.Order(
        patient_id=patient.id,
        accession=f'SEL-ACC-{suffix}',
        modality='DX',
        procedure='Selection Search Exam',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )
    m.db.session.add(order)
    m.db.session.commit()
    return patient,order


def test_cancellation_search_supports_all_required_order_keys(app_ctx):
    patient,order=_case('7701')
    terms=(
        order.accession,
        patient.patient_id,
        patient.name,
        patient.phone,
        str(order.id),
    )
    for term in terms:
        orders,_appointments=m.cancellation_search_rows(term)
        assert order.id in [row.id for row in orders], term


def test_cancellation_search_phone_can_be_partial(app_ctx):
    patient,order=_case('7702')
    orders,_appointments=m.cancellation_search_rows(patient.phone[-6:])
    assert order.id in [row.id for row in orders]


def test_cancellation_search_escapes_like_wildcards(app_ctx):
    _patient,order=_case('7703')
    for term in ('%','_'):
        orders,_appointments=m.cancellation_search_rows(term)
        assert order.id not in [row.id for row in orders]


def test_cancellation_search_order_id_is_exact_not_partial(app_ctx):
    _patient,order=_case('7704')
    orders,_appointments=m.cancellation_search_rows(str(order.id))
    assert order.id in [row.id for row in orders]


def test_cancellation_and_data_deletion_centers_are_separated(app_ctx):
    admin=_admin()
    _patient,order=_case('7705')
    client=m.app.test_client()
    _login(client,admin)

    cancellation=client.get(
        '/admin/cancellation-center?q=SEL-ACC-7705'
    )
    assert cancellation.status_code==200
    assert b'Select case &amp; review dependencies' not in cancellation.data
    assert b'Cancel order' in cancellation.data
    assert b'Data Deletion Center' in cancellation.data

    deletion=client.get(
        '/admin/data-deletion-center?q=SEL-ACC-7705'
    )
    assert deletion.status_code==200
    assert b'Search &amp; Case Selection' in deletion.data
    assert b'Accession / Patient ID / Name / Phone / Order ID' in deletion.data
    assert b'Select case &amp; review dependencies' in deletion.data
    assert b'Cancel order' not in deletion.data
    assert b'Cancel booking' not in deletion.data

    expected=(
        f'/admin/cancellation-center/order/{order.id}/preview'
        .encode()
    )
    assert expected in deletion.data


def test_cancellation_search_and_selection_is_read_only(app_ctx):
    admin=_admin()
    patient,order=_case('7706')
    client=m.app.test_client()
    _login(client,admin)

    before=(
        m.Order.query.count(),
        m.Patient.query.count(),
        m.Report.query.count(),
        m.AuditLog.query.count(),
        order.status,
    )

    response=client.get(f'/admin/cancellation-center?q={patient.phone}')
    assert response.status_code==200

    preview=client.get(
        f'/admin/cancellation-center/order/{order.id}/preview?format=json'
    )
    assert preview.status_code==200
    assert preview.get_json()['readonly'] is True

    m.db.session.refresh(order)
    after=(
        m.Order.query.count(),
        m.Patient.query.count(),
        m.Report.query.count(),
        m.AuditLog.query.count(),
        order.status,
    )
    assert after==before

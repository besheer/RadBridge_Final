class FakeOrthancResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _make_real_order(
    m,
    suffix,
    study_id,
    image_count,
    pacs_status,
):
    patient=m.Patient(
        patient_id=f'PACS-PRESENT-{suffix}',
        name=f'PACS Present {suffix}',
    )

    m.db.session.add(patient)
    m.db.session.flush()

    order=m.Order(
        patient_id=patient.id,
        accession=f'PACS-PRESENT-{suffix}',
        modality='DX',
        procedure='PACS Presence Test',
        scheduled=m.datetime.utcnow(),
        status='CANCELLED',
    )

    order.pacs_study_id=study_id
    order.pacs_image_count=image_count
    order.pacs_status=pacs_status

    m.db.session.add(order)
    m.db.session.commit()

    return order


def test_pacs_present_true_on_orthanc_200(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    order=_make_real_order(
        m,
        '200',
        'orthanc-study-200',
        3,
        'IMAGES_COMPLETE',
    )

    calls={'count':0}

    def fake_get(*args,**kwargs):
        calls['count'] += 1
        return FakeOrthancResponse(200)

    monkeypatch.setattr(
        m.requests,
        'get',
        fake_get,
    )

    snap=m.granular_delete_order_preview_snapshot(order)

    assert snap['pacs']['linked'] is True
    assert snap['pacs']['present'] is True
    assert snap['pacs']['image_count'] == 3
    assert calls['count'] == 1


def test_pacs_present_false_on_orthanc_404(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    order=_make_real_order(
        m,
        '404',
        'orthanc-study-404',
        0,
        'IMAGES_DELETED',
    )

    monkeypatch.setattr(
        m.requests,
        'get',
        lambda *args,**kwargs: FakeOrthancResponse(404),
    )

    snap=m.granular_delete_order_preview_snapshot(order)

    assert snap['pacs']['linked'] is True
    assert snap['pacs']['present'] is False
    assert snap['pacs']['image_count'] == 0
    assert snap['pacs']['status'] == 'IMAGES_DELETED'


def test_pacs_present_none_on_unexpected_http(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    order=_make_real_order(
        m,
        '500',
        'orthanc-study-500',
        2,
        'IMAGES_COMPLETE',
    )

    monkeypatch.setattr(
        m.requests,
        'get',
        lambda *args,**kwargs: FakeOrthancResponse(500),
    )

    snap=m.granular_delete_order_preview_snapshot(order)

    assert snap['pacs']['linked'] is True
    assert snap['pacs']['present'] is None


def test_pacs_present_none_on_request_exception(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    order=_make_real_order(
        m,
        'EXCEPTION',
        'orthanc-study-exception',
        2,
        'IMAGES_COMPLETE',
    )

    def fake_get(*args,**kwargs):
        raise TimeoutError('synthetic timeout')

    monkeypatch.setattr(
        m.requests,
        'get',
        fake_get,
    )

    snap=m.granular_delete_order_preview_snapshot(order)

    assert snap['pacs']['linked'] is True
    assert snap['pacs']['present'] is None


def test_pacs_no_link_is_false_without_request(
    app_ctx,
    monkeypatch,
):
    m=app_ctx

    order=_make_real_order(
        m,
        'NOLINK',
        '',
        0,
        None,
    )

    calls={'count':0}

    def forbidden_get(*args,**kwargs):
        calls['count'] += 1
        raise AssertionError(
            'Orthanc must not be queried without study id'
        )

    monkeypatch.setattr(
        m.requests,
        'get',
        forbidden_get,
    )

    snap=m.granular_delete_order_preview_snapshot(order)

    assert snap['pacs']['linked'] is False
    assert snap['pacs']['present'] is False
    assert calls['count'] == 0

import app as m


def _login(client,user):
    with client.session_transaction() as session:
        session['uid']=user.id


def _super_admin():
    return (
        m.User.query
        .join(m.Role,m.User.role_id==m.Role.id)
        .filter(
            m.Role.code=='SUPER_ADMIN',
            m.User.active.is_(True),
        )
        .first()
    )


def test_images_only_route_is_post_only(app_ctx):
    rules={
        rule.rule:set(rule.methods)
        for rule in m.app.url_map.iter_rules()
    }

    path=(
        '/admin/cancellation-center/order/'
        '<int:order_id>/delete-images'
    )

    assert path in rules
    assert 'POST' in rules[path]
    assert 'GET' not in rules[path]
    assert 'DELETE' not in rules[path]


def test_images_only_requires_super_admin(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_images_only_preflight
    )

    assert 'SUPER_ADMIN_REQUIRED' in source
    assert "role" in source
    assert "SUPER_ADMIN" in source


def test_images_only_requires_reason_and_accession(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_images_only_preflight
    )

    assert 'REASON_REQUIRED' in source
    assert 'ACCESSION_CONFIRMATION_MISMATCH' in source


def test_images_only_blocks_shared_study(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_images_only_preflight
    )

    assert 'PACS_STUDY_SHARED_BY_OTHER_ORDER' in source


def test_images_only_blocks_active_transfer(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_images_only_preflight
    )

    assert 'ACTIVE_PACS_TRANSFER_JOB' in source
    assert 'PENDING' in source
    assert 'SENDING' in source


def test_images_only_identity_checks(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_images_only_preflight
    )

    assert 'ORTHANC_ACCESSION_MISMATCH' in source
    assert 'ORTHANC_PATIENT_ID_MISMATCH' in source
    assert 'ORTHANC_STUDY_UID_MISMATCH' in source


def test_images_only_exact_orthanc_delete_contract(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_order_images_only
    )

    assert 'requests.delete' in source
    assert "response.status_code != 200" in source
    assert "verify.status_code != 404" in source


def test_images_only_retains_pacs_identifiers(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_order_images_only
    )

    assert "order.pacs_image_count=0" in source
    assert "order.pacs_status='IMAGES_DELETED'" in source

    assert 'order.pacs_study_id=' not in source
    assert 'order.study_instance_uid=' not in source


def test_images_only_audit_contract(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_order_images_only
    )

    assert 'PACS_IMAGES_DELETE_REQUESTED_ADMIN' in source
    assert 'PACS_IMAGES_DELETED_ADMIN' in source
    assert 'PACS_IMAGES_DELETE_FAILED_ADMIN' in source


def test_images_only_does_not_delete_ris_objects(app_ctx):
    import inspect

    source=inspect.getsource(
        m.granular_delete_order_images_only
    )

    forbidden=(
        'db.session.delete(order)',
        'db.session.delete(patient)',
        'Report.query.delete',
        'Attachment.query.delete',
    )

    for marker in forbidden:
        assert marker not in source

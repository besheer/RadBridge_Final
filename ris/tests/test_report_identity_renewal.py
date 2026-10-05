from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from itsdangerous import URLSafeTimedSerializer
from itsdangerous.timed import TimestampSigner


@pytest.fixture
def renewal(app_ctx, monkeypatch):
    m = app_ctx
    user = SimpleNamespace(id=41, active=True, branch_id=2,
                           role=SimpleNamespace(code='RADIOLOGIST'))
    order = SimpleNamespace(id=9, branch_id=2, assigned_doctor_id=41)
    serializer = URLSafeTimedSerializer('unit-test-only', salt='test-renewal')
    monkeypatch.setattr(m, 'current_user', lambda: user)
    monkeypatch.setattr(m, 'has_perm', lambda perm: perm == 'reports.view')
    monkeypatch.setattr(m, '_ohif_identity_serializer', lambda: serializer)
    monkeypatch.setattr(m.db.session, 'get', lambda model, oid: order if oid == 9 else None)
    monkeypatch.setattr(m, 'validate_ohif_case_context', lambda row: (
        m.request.args.get('StudyInstanceUIDs') == '1.2.3', {'error': 'OHIF_STUDY_ORDER_MISMATCH'}))
    monkeypatch.setattr(m, 'create_ohif_doctor_identity', lambda actor, row: 'fresh-test-identity')
    monkeypatch.setattr(m, 'audit_as_user', Mock())
    monkeypatch.setattr(m.db.session, 'commit', Mock())
    payload = dict(purpose='OHIF_REPORTING', user_id=41, order_id=9, role='RADIOLOGIST')
    return m, user, order, serializer, payload


def invoke(fixture, *, payload=None, token=None, uid='1.2.3', oid=9):
    m, _, _, serializer, default = fixture
    token = token if token is not None else serializer.dumps(default if payload is None else payload)
    with m.app.test_request_context(
            f'/api/reporting/identity/{oid}?StudyInstanceUIDs={uid}', method='POST',
            headers={'X-RadBridge-Doctor-Identity': token}):
        response = m.app.view_functions['report_identity.renew'](oid)
        assert response.headers['Cache-Control'] == 'no-store'
        assert response.headers['Vary'] == 'Cookie'
        return response


def test_valid_renewal_is_audited_without_token(renewal):
    m, *_ = renewal
    response = invoke(renewal)
    assert response.status_code == 200
    assert response.json['identity'] == 'fresh-test-identity'
    assert response.json['expires_in'] == m.OHIF_DOCTOR_IDENTITY_MAX_AGE
    assert 'fresh-test-identity' not in str(m.audit_as_user.call_args)
    m.db.session.commit.assert_called_once()


def test_expired_identity_only_renews_with_active_same_subject(renewal, monkeypatch):
    _, _, _, serializer, payload = renewal
    with monkeypatch.context() as patch:
        patch.setattr(TimestampSigner, 'get_timestamp', lambda self: 100)
        token = serializer.dumps(payload)
    from itsdangerous import SignatureExpired
    with pytest.raises(SignatureExpired):
        serializer.loads(token, max_age=300)
    assert invoke(renewal, token=token).status_code == 200


@pytest.mark.parametrize('change', [dict(user_id=42), dict(order_id=10),
    dict(role='CONSULTANT'), dict(purpose='OTHER'), dict(user_id=None)])
def test_wrong_subject_order_role_or_purpose_is_denied(renewal, change):
    payload = dict(renewal[-1], **change)
    assert invoke(renewal, payload=payload).status_code == 403
    renewal[0].audit_as_user.assert_not_called()
    renewal[0].db.session.commit.assert_not_called()


@pytest.mark.parametrize('token', ['', 'tampered', '[]'])
def test_invalid_signature_denied(renewal, token):
    assert invoke(renewal, token=token).status_code == 403


@pytest.mark.parametrize('boundary', ['session', 'inactive', 'permission', 'role', 'assignment', 'branch', 'study', 'missing_order'])
def test_live_authorization_and_study_are_rechecked(renewal, monkeypatch, boundary):
    m, user, order, *_ = renewal
    if boundary == 'session': monkeypatch.setattr(m, 'current_user', lambda: None)
    if boundary == 'inactive': user.active = False
    if boundary == 'permission': monkeypatch.setattr(m, 'has_perm', lambda _: False)
    if boundary == 'role': user.role.code = 'TECHNICIAN'
    if boundary == 'assignment': order.assigned_doctor_id = 99
    if boundary == 'branch': order.branch_id = 3
    response = invoke(renewal, uid='wrong' if boundary == 'study' else '1.2.3',
                      oid=99 if boundary == 'missing_order' else 9)
    assert response.status_code in (401, 403, 409)
    m.db.session.commit.assert_not_called()
    m.audit_as_user.assert_not_called()


def test_get_does_not_issue_identity(renewal):
    with renewal[0].app.test_client() as client:
        assert client.get('/api/reporting/identity/9').status_code == 405

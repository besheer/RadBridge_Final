import os
import sys
import pytest

from application.legacy_runtime import resolve_runtime
from infrastructure.extensions import db
from web.factory import create_clinical_app, dispose_clinical_app


def make_app(tmp_path, name):
    return create_clinical_app({
        'DATABASE_URL': 'sqlite:///:memory:', 'SECRET_KEY': 'SYNTHETIC-' + name,
        'REPORT_DIR': str(tmp_path / name / 'reports'),
        'ATTACHMENT_DIR': str(tmp_path / name / 'attachments'),
        'BACKUP_DIR': str(tmp_path / name / 'backups'),
        'RIS_PUBLIC_URL': 'http://localhost', 'SESSION_COOKIE_SECURE': '0',
        'ORTHANC_URL': 'http://127.0.0.1:9', 'PACS_ORTHANC_URL': 'http://127.0.0.1:9',
    })


def seed(app, name):
    runtime = app.extensions['radbridge_runtime']
    with app.app_context():
        assert resolve_runtime() is runtime
        db.create_all()
        branch = runtime.Branch(code='SYNTHETIC', name=name)
        role = runtime.Role(code='SUPER_ADMIN', name='Synthetic admin', permissions_json='["*"]')
        db.session.add_all([branch, role]); db.session.flush()
        user = runtime.User(username='same-user', full_name=name, password_hash='synthetic-session-only',
                            role_id=role.id, branch_id=branch.id, active=True)
        db.session.add(user)
        db.session.add(runtime.CompanyProfile(name_en=name, name_ar=name))
        db.session.commit()
        profile = runtime.get_user_profile(user)
        profile.settings_json = '{"contacts":{"email":"' + name + '@example.invalid"}}'
        db.session.commit()
        return user.id


def test_two_clinical_runtimes_keep_data_sessions_settings_and_role_state_separate(tmp_path, app_ctx):
    environment_before = dict(os.environ)
    first, second = make_app(tmp_path, 'first-clinician'), make_app(tmp_path, 'second-clinician')
    try:
        a, b = first.extensions['radbridge_runtime'], second.extensions['radbridge_runtime']
        assert a is not b and a is not app_ctx
        assert first.secret_key != second.secret_key
        assert a.REPORT_DIR != b.REPORT_DIR
        assert a.ROLE_PERMS is not b.ROLE_PERMS
        assert a.ALL_PERMISSIONS is not b.ALL_PERMISSIONS
        a.ROLE_PERMS['TECHNICIAN'].append('SYNTHETIC-INSTANCE-PERMISSION')
        assert 'SYNTHETIC-INSTANCE-PERMISSION' not in b.ROLE_PERMS['TECHNICIAN']
        assert sorted((r.rule, r.endpoint, sorted(r.methods)) for r in first.url_map.iter_rules()) == sorted(
            (r.rule, r.endpoint, sorted(r.methods)) for r in app_ctx.app.url_map.iter_rules())
        ids = seed(first, 'first-clinician'), seed(second, 'second-clinician')
        for app, uid, own, other in ((first, ids[0], 'first-clinician', 'second-clinician'),
                                     (second, ids[1], 'second-clinician', 'first-clinician')):
            client = app.test_client()
            with client.session_transaction() as session:
                session['uid'] = uid
            response = client.get('/admin/users')
            assert response.status_code == 200
            assert own in response.text and other not in response.text
            with app.app_context():
                assert resolve_runtime().Branch.query.one().name == own
                import user_access_policy
                assert user_access_policy.contacts(resolve_runtime().User.query.one())['email'] == own + '@example.invalid'
        assert dict(os.environ) == environment_before
    finally:
        dispose_clinical_app(first); dispose_clinical_app(second)
    assert a.__name__ not in sys.modules and b.__name__ not in sys.modules


def test_factory_cannot_enable_bootstrap_or_accept_unknown_instance_configuration():
    with pytest.raises(ValueError, match='Unsupported'):
        create_clinical_app({'RADBRIDGE_BOOTSTRAP_ON_IMPORT': '1'})
    with pytest.raises(TypeError):
        create_clinical_app({'SECRET_KEY': None})


def test_clinical_query_scope_listeners_run_only_for_their_own_application(tmp_path, app_ctx, monkeypatch):
    import json
    import clinical_scope
    first, second = make_app(tmp_path, 'scope-one'), make_app(tmp_path, 'scope-two')
    try:
        actors = seed(first, 'scope-one'), seed(second, 'scope-two')
        for app in (first, second):
            with app.app_context():
                runtime = resolve_runtime()
                profile = runtime.get_user_profile(runtime.User.query.one())
                profile.settings_json = json.dumps({'clinical_scope': {
                    'enabled': True, 'modalities': ['CT'], 'device_keys': [], 'room_keys': [], 'device_ids': []
                }})
                db.session.commit()
        original = clinical_scope.predicate
        observed = []

        def traced(runtime, scope, *args, **kwargs):
            observed.append(runtime.app)
            return original(runtime, scope, *args, **kwargs)

        monkeypatch.setattr(clinical_scope, 'predicate', traced)
        for app, uid in zip((first, second), actors):
            observed.clear()
            client = app.test_client()
            with client.session_transaction() as session:
                session['uid'] = uid
            assert client.get('/patients').status_code == 200
            assert observed and all(owner is app for owner in observed)
    finally:
        dispose_clinical_app(first); dispose_clinical_app(second)

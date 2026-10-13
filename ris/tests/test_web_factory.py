from infrastructure.settings import WebSettings
from web.factory import create_web_app


def test_web_shells_have_independent_configuration_and_no_clinical_side_effects(tmp_path):
    first = create_web_app('synthetic_one', root_path=tmp_path, settings=WebSettings.from_environment({
        'SECRET_KEY': 'synthetic-one', 'DATABASE_URL': 'sqlite:///:memory:', 'RIS_PUBLIC_URL': 'http://localhost'
    }))
    second = create_web_app('synthetic_two', root_path=tmp_path, settings=WebSettings.from_environment({
        'SECRET_KEY': 'synthetic-two', 'DATABASE_URL': 'sqlite:///:memory:', 'RIS_PUBLIC_URL': 'https://example.invalid'
    }))
    assert first.secret_key == 'synthetic-one'
    assert second.secret_key == 'synthetic-two'
    assert first.config['SESSION_COOKIE_SECURE'] is False
    assert second.config['SESSION_COOKIE_SECURE'] is True
    first.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
    assert second.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert not first.extensions
    assert not list(tmp_path.iterdir())


def test_explicit_cookie_override_preserves_legacy_semantics():
    settings = WebSettings.from_environment({'RIS_PUBLIC_URL': 'https://example.invalid', 'SESSION_COOKIE_SECURE': '0'})
    assert settings.session_cookie_secure is False
    assert WebSettings.from_environment({'RIS_PUBLIC_URL': 'http://localhost', 'SESSION_COOKIE_SECURE': '1'}).session_cookie_secure

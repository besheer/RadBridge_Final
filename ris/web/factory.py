"""Create the HTTP shell without database writes, workers or external requests.

Clinical components are installed by the composition root. This shell factory
alone is not the fully composed clinical application factory.
"""
from flask import Flask

from infrastructure.settings import WebSettings


def create_web_app(import_name, *, root_path, settings):
    app = Flask(import_name, root_path=str(root_path))
    app.config.update(settings.flask_config())
    return app


CLINICAL_SETTINGS = frozenset({
    'SECRET_KEY', 'DATABASE_URL', 'REPORT_DIR', 'ATTACHMENT_DIR', 'BACKUP_DIR',
    'SESSION_COOKIE_SAMESITE', 'SESSION_COOKIE_SECURE', 'RIS_PUBLIC_URL',
    'ORTHANC_URL', 'ORTHANC_PUBLIC_URL', 'PACS_ORTHANC_URL',
    'OHIF_PUBLIC_URL', 'OHIF_INTERNAL_URL',
    'ONLYOFFICE_INTERNAL_URL', 'ONLYOFFICE_RIS_INTERNAL_URL',
})


def create_clinical_app(configuration=None):
    """Compose a fresh clinical runtime without changing env or bootstrapping DB.

    Only explicit runtime settings are configurable per instance; remaining
    provider/host feature configuration is process-level. Existing app:app and
    worker CLIs remain available as compatibility entry points.
    """
    import importlib.util
    import os
    import sys
    import uuid
    from application.legacy_runtime import BUILD_RUNTIME
    from infrastructure.composition_environment import BUILD_ENVIRONMENT
    from infrastructure.resources import RIS_ROOT

    configuration = dict(configuration or {})
    unknown = set(configuration) - CLINICAL_SETTINGS
    if unknown:
        raise ValueError('Unsupported per-instance settings: ' + ', '.join(sorted(unknown)))
    if any(not isinstance(value, str) for value in configuration.values()):
        raise TypeError('Clinical settings must be strings')
    environment = dict(os.environ)
    environment.update(configuration)
    environment['RADBRIDGE_BOOTSTRAP_ON_IMPORT'] = '0'
    name = '_radbridge_runtime_' + uuid.uuid4().hex
    specification = importlib.util.spec_from_file_location(name, RIS_ROOT / 'app.py')
    runtime = importlib.util.module_from_spec(specification)
    sys.modules[name] = runtime
    environment_token = BUILD_ENVIRONMENT.set(environment)
    runtime_token = BUILD_RUNTIME.set(runtime)
    try:
        specification.loader.exec_module(runtime)
        runtime.app.extensions['radbridge_factory_instance'] = True
        return runtime.app
    except BaseException:
        if hasattr(runtime, 'app'):
            _dispose_runtime(runtime.app)
        sys.modules.pop(name, None)
        raise
    finally:
        BUILD_RUNTIME.reset(runtime_token)
        BUILD_ENVIRONMENT.reset(environment_token)


def _dispose_runtime(app):
    from sqlalchemy import event
    from infrastructure.extensions import db
    for target, event_name, listener in app.extensions.pop('radbridge_orm_listeners', []):
        event.remove(target, event_name, listener)
    if 'sqlalchemy' in app.extensions:
        with app.app_context():
            db.session.remove()
            for engine in db.engines.values():
                engine.dispose()


def dispose_clinical_app(app):
    """Release a stopped factory instance; never disposes legacy app:app."""
    import sys
    if not app.extensions.get('radbridge_factory_instance'):
        raise ValueError('Only factory-created instances can be disposed here')
    _dispose_runtime(app)
    runtime = app.extensions['radbridge_runtime']
    sys.modules.pop(runtime.__name__, None)
    app.extensions['radbridge_disposed'] = True

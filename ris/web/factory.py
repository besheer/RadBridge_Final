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

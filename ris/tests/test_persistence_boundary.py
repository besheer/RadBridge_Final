"""Persistence can be loaded and used without booting the clinical web runtime."""
import subprocess
import sys
from pathlib import Path


def test_standalone_schema_and_separate_application_databases():
    code = '''
import sys
from flask import Flask
from infrastructure.extensions import db
from infrastructure.models import Branch, Patient, Order, Report, ReportVersion
assert "app" not in sys.modules
apps = []
for i in range(2):
    app = Flask("synthetic-persistence-" + str(i))
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    apps.append(app)
with apps[0].app_context():
    db.create_all()
    db.session.add(Branch(code="SYNTHETIC-ISOLATED", name="SYNTHETIC INDEPENDENT DB"))
    db.session.commit()
    assert Branch.query.count() == 1
with apps[1].app_context():
    db.create_all()
    assert Branch.query.count() == 0
with apps[0].app_context():
    assert Branch.query.count() == 1
'''
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

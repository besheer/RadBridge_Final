
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]

def test_app_python_parses():
    ast.parse((ROOT/"app.py").read_text(encoding="utf-8"))

def test_critical_templates_exist():
    required=[
        "base.html","patient_form.html","order_detail.html",
        "technician.html","patient_portal.html","financial_center.html"
    ]
    for name in required:
        assert (ROOT/"templates"/name).exists(), name

def test_critical_features_present():
    s=(ROOT/"app.py").read_text(encoding="utf-8")
    for token in [
        "def nursing_worklist(",
        "def pacs_tracking(",
        "def patient_portal(",
        "def financial_center(",
        "def admin_company(",
        "def pacs_reconciliation(",
    ]:
        assert token in s, token

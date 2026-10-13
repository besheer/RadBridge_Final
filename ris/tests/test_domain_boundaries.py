"""Load all business policy boundaries with third-party packages unavailable."""
from pathlib import Path
import subprocess
import sys


def test_domain_policies_load_without_framework_database_or_network_clients():
    root = Path(__file__).resolve().parents[1]
    code = '''
import sys
from domain.clinical.workflow import can_transition
from domain.clinical.images import completion_image_policy
from domain.assignment.decision import evaluate_assignment_decision
from domain.registration import demographics, exam_types, intake
from domain.imaging import resolution
from domain.reporting import transitions, content
from domain import readiness, readiness_checks
assert not can_transition("NURSING", "ORDERED", "REPORTING").allowed
assert not can_transition("TECHNICIAN", "ORDERED", "FINAL").allowed
assert not completion_image_policy(matched=False,pacs_present=True,error=False,image_count=100,policy_defined=True)["allowed"]
for name in ("flask", "sqlalchemy", "requests", "app"):
    assert name not in sys.modules
'''
    result = subprocess.run([sys.executable, "-S", "-c", code], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

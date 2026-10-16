"""Behavioral contracts for the readiness boundary; no changed policy rules."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from domain import readiness
import case_readiness_service as legacy

BASE = dict(image_count=4, min_images=3, warning_images=5,
            require_pacs=True, pacs_present=True, require_history=True,
            history_present=True, require_attachments=True, attachment_count=1,
            required_series="PA/AP,LATERAL", series=[
                {"series_id":"synthetic-1", "description":"AP CHEST", "instance_count":2},
                {"series_id":"synthetic-2", "description":"LATERAL CHEST", "instance_count":2}])

@pytest.mark.parametrize("changes,status,blockers", [
    ({}, "WARNING", []),
    ({"image_count":5}, "READY", []),
    ({"image_count":2}, "BLOCKED", ["INCOMPLETE_IMAGES"]),
    ({"pacs_present":False}, "BLOCKED", ["MISSING_PACS"]),
    ({"history_present":False}, "BLOCKED", ["MISSING_HISTORY"]),
    ({"attachment_count":0}, "BLOCKED", ["MISSING_ATTACHMENTS"]),
    ({"series":[]}, "BLOCKED", ["MISSING_SERIES"]),
    ({"image_count":2,"history_present":False}, "BLOCKED", ["MISSING_HISTORY","INCOMPLETE_IMAGES"]),
])
def test_readiness_contract(changes,status,blockers):
    result=readiness.evaluate_readiness(**(BASE|changes))
    assert result["status"]==status
    assert result["details"]["blockers"]==blockers
    assert result["score"]==100-20*len(blockers)
    assert len(result["facts_sha256"])==64

def test_evidence_is_stable_and_input_not_mutated():
    before=json.dumps(BASE,sort_keys=True)
    first=readiness.evaluate_readiness(**BASE)
    again=readiness.evaluate_readiness(**BASE)
    assert first==again
    assert json.dumps(BASE,sort_keys=True)==before
    changed=readiness.evaluate_readiness(**(BASE|{"image_count":5}))
    assert changed["facts_sha256"]!=first["facts_sha256"]

def test_legacy_facade_keeps_function_identity():
    assert legacy.evaluate_readiness is readiness.evaluate_readiness
    assert legacy.evaluate_required_series is readiness.evaluate_required_series
    assert legacy.required_series_groups is readiness.required_series_groups
    assert legacy._norm is readiness._norm

def test_domain_imports_without_site_packages_or_app():
    root=str(Path(__file__).resolve().parents[1])
    code="import sys;sys.path.insert(0,"+repr(root)+");from domain.readiness import required_series_groups;assert required_series_groups('PA/AP,LATERAL')==[['PA','AP'],['LATERAL']];assert 'app' not in sys.modules;assert 'flask' not in sys.modules;assert 'sqlalchemy' not in sys.modules"
    p=subprocess.run([sys.executable,"-S","-c",code],capture_output=True,text=True)
    assert p.returncode==0,p.stderr

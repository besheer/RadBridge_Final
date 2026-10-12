import importlib.util
import json
from pathlib import Path
import pytest


@pytest.mark.parametrize('source',['import flask\n','from sqlalchemy import text\n','from application.legacy_runtime import resolve_runtime\n'])
def test_declared_context_helper_cannot_hide_framework_or_runtime_dependency(tmp_path,source):
    spec=importlib.util.spec_from_file_location('isolated_architecture_checker',Path(__file__).resolve().parents[2]/'tools/check_architecture.py')
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    checker.ROOT=tmp_path
    helper=tmp_path/'application/services/synthetic_helper.py'
    helper.parent.mkdir(parents=True)
    helper.write_text(source,encoding='utf-8')
    (tmp_path/'application/port_contracts.json').write_text(json.dumps(dict(services=[],helpers=['application.services.synthetic_helper'])),encoding='utf-8')
    errors=checker.violations()
    assert any('synthetic_helper.py' in error and 'explicit boundary imports' in error for error in errors)

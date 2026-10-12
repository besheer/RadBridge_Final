"""HTTP placement guard covers unregistered services, not just declared ports."""
import importlib.util
import json
from pathlib import Path
import pytest


def checker_at(tmp_path):
    spec=importlib.util.spec_from_file_location('synthetic_http_checker',Path(__file__).resolve().parents[2]/'tools/check_architecture.py')
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    checker.ROOT=tmp_path
    (tmp_path/'application').mkdir()
    (tmp_path/'application/port_contracts.json').write_text(json.dumps({'services':[]}),encoding='utf-8')
    return checker


@pytest.mark.parametrize('source',['import flask\n','from flask import request\n'])
def test_unregistered_service_cannot_bypass_http_import_guard(tmp_path,source):
    checker=checker_at(tmp_path)
    service=tmp_path/'application/services/unregistered.py';service.parent.mkdir()
    service.write_text(source,encoding='utf-8')
    assert any('application service imports HTTP framework' in error for error in checker.violations())


def test_web_owner_may_import_http_framework(tmp_path):
    checker=checker_at(tmp_path)
    owner=tmp_path/'web/extensions/synthetic.py';owner.parent.mkdir(parents=True)
    owner.write_text('from flask import request\n',encoding='utf-8')
    assert checker.violations()==[]

"""Safety findings are redacted and examples still receive content checks."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('source_safety',Path(__file__).resolve().parents[2]/'tools/check_source_safety.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


@pytest.mark.parametrize('path',['.env','ris/.env.local','ris/pacs.env','secrets/credentials.txt','report-files/report.docx','attachments/upload.pdf','backups/backup.tar.gz','private.key','image.dcm','data.sqlite3'])
def test_sensitive_paths_are_rejected(path):
    assert guard.forbidden_path(path)


@pytest.mark.parametrize('path',['development/.env.example','ris/requirements.txt','ris/assets/fonts/font.ttf','ris/migrations/schema.sql'])
def test_source_and_dummy_configuration_paths_allowed(path):
    assert not guard.forbidden_path(path)


def test_example_file_with_provider_shaped_token_is_not_exempt_and_output_is_redacted():
    token=b'ghp_'+b'A'*36
    findings=guard.inspect_bytes('development/.env.example',b'first line\nTOKEN='+token)
    assert findings==[{'path':'development/.env.example','rule':'github-token','line':2}]
    assert token.decode() not in str(findings)


def test_private_key_content_in_unexpected_extension_is_blocked():
    header=b'-'*5+b'BEGIN PRIVATE KEY'+b'-'*5
    findings=guard.inspect_bytes('configuration.txt',header+b'\n'+b'A'*64+b'\n')
    assert findings[0]['rule']=='private-key'


def test_literal_placeholder_is_not_reported_as_real_provider_token():
    assert guard.inspect_bytes('example.txt',b'TOKEN=<your-token>\nghp_placeholder')==[]

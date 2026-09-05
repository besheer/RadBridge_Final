from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
BASE=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')

def test_release_metadata():
    assert "APP_VERSION = '5.46.9'" in APP
    assert "BUILD_NAME = 'fresh-schema-runtime-hardening'" in APP

def test_patient_get_redirects_to_unified_registration():
    s=APP[APP.index('def new_patient():'):APP.index('def new_patient():')+1200]
    assert "request.method=='GET'" in s
    assert "schedule_calendar" in s
    assert "open_registration='1'" in s

def test_feature_groups_present():
    for x in ['Reception','Clinical','PACS & Imaging','Operations','Finance','Inventory','Communications','Management','Administration']:
        assert x in BASE

def test_key_recovered_links_present():
    for ep in ['workflow_command_center','financial_center','inventory_ledger','pacs_reconciliation','communications_dashboard','management_dashboard','coordinator_queue','smart_intake_start']:
        assert "url_for(\\'%s\\')"%ep in BASE or "url_for('%s')"%ep in BASE

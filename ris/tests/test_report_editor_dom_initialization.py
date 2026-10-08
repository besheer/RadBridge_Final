"""Browser-order regression; real lease writes additionally require isolated PostgreSQL."""
from html.parser import HTMLParser
from pathlib import Path
import pytest
import app as m
from test_doctor_unified_workspace import workspace

class EditorDOM(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=set(); self.dictate=0; self.scripts=[]
        self.current=None; self.form=None; self.web_fields={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('id'):self.ids.add(a['id'])
        if 'data-dictate' in a:self.dictate+=1
        if tag=='form':self.form=a.get('id')
        if tag=='input' and self.form=='web-report-form' and a.get('name'):
            self.web_fields[a['name']]=a.get('value','')
        if tag=='script':self.current={'text':'','ids_before':set(self.ids),'dictate_before':self.dictate}
    def handle_data(self,data):
        if self.current is not None:self.current['text']+=data
    def handle_endtag(self,tag):
        if tag=='script' and self.current is not None:self.scripts.append(self.current);self.current=None
        if tag=='form':self.form=None

def page(w):
    r=w.client.get(f'/reports/{w.mine.id}');assert r.status_code==200
    dom=EditorDOM();dom.feed(r.text);return dom

@pytest.fixture
def postgres_workspace(workspace):
    # The real lease uses PostgreSQL FOR UPDATE; never stub its safety boundary.
    if m.db.engine.dialect.name!='postgresql':
        pytest.skip('Run against disposable PostgreSQL for real row-lock/lease integration')
    return workspace

@pytest.mark.parametrize('lang',['ar','en'])
def test_editor_controls_exist_before_inline_initializers(workspace,monkeypatch,lang):
    w=workspace;monkeypatch.setattr(m,'current_ui_language',lambda:lang)
    dom=page(w)
    lease=[s for s in dom.scripts if "const form = document.getElementById('web-report-form')" in s['text']]
    dictation=[s for s in dom.scripts if "document.querySelectorAll('[data-dictate]')" in s['text']]
    assert len(lease)==len(dictation)==1
    assert {'web-report-form','web-lease-token','upload-lease-token','rb-report-lease-status'} <= lease[0]['ids_before']
    assert {'dictationStatus','dictationLanguage'} <= dictation[0]['ids_before']
    assert dictation[0]['dictate_before']==2

def test_real_draft_save_with_acquired_lease(postgres_workspace,monkeypatch,tmp_path):
    w=postgres_workspace;monkeypatch.setattr(m,'REPORT_DIR',str(tmp_path))
    dom=page(w)
    response=w.client.post(f'/reports/{w.mine.id}/lease/acquire',json={'editor_type':'BROWSER'})
    assert response.status_code==200 and response.json['ok']
    payload={**dom.web_fields,'lease_token':response.json['lease_token'],
             'action':'DRAFT','radiologist':'Synthetic UAT Doctor',
             'findings':'SYNTHETIC DOM FIX SAVE','impression':'TRAINING ONLY'}
    saved=w.client.post(f'/reports/{w.mine.id}',data=payload)
    assert saved.status_code==302
    report=m.Report.query.filter_by(order_id=w.mine.id).one()
    assert report.status=='DRAFT' and report.findings=='SYNTHETIC DOM FIX SAVE'
    assert m.ReportVersion.query.filter_by(report_id=report.id).count()==1

def test_missing_lease_still_cannot_modify_report(workspace):
    w=workspace;dom=page(w)
    w.client.post(f'/reports/{w.mine.id}',data={**dom.web_fields,'action':'DRAFT','findings':'DENIED_SYNTHETIC_WRITE'})
    assert m.Report.query.filter_by(order_id=w.mine.id).one().findings!='DENIED_SYNTHETIC_WRITE'

def test_other_editors_lease_still_blocks_acquire(postgres_workspace):
    w=postgres_workspace;page(w);w.login(w.admin)
    assert w.client.post(f'/reports/{w.mine.id}/lease/acquire',json={'editor_type':'BROWSER'}).status_code==200
    w.login(w.doctor)
    blocked=w.client.post(f'/reports/{w.mine.id}/lease/acquire',json={'editor_type':'BROWSER'})
    assert blocked.status_code==409 and blocked.json['error']=='REPORT_EDIT_LOCKED'

def test_final_editor_has_no_acquisition_script_and_cannot_save(workspace):
    w=workspace;report=m.get_report(w.mine);report.status='FINAL';report.findings='IMMUTABLE_SYNTHETIC_FINAL';m.db.session.commit()
    dom=page(w)
    assert not any('const acquireUrl =' in s['text'] for s in dom.scripts)
    w.client.post(f'/reports/{w.mine.id}',data={**dom.web_fields,'action':'DRAFT','findings':'DENIED_FINAL_WRITE'})
    assert report.findings=='IMMUTABLE_SYNTHETIC_FINAL'

def test_foreign_case_direct_url_still_denied(workspace):
    w=workspace
    assert w.client.get(f'/reports/{w.foreign.id}').status_code==403

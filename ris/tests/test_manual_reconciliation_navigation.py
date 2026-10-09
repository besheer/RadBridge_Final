import pytest
import app as m
from test_dicom_reconciliation import isolated, setup, SOURCE

@pytest.mark.parametrize('lang',['en','ar'])
def test_manual_study_selection_keeps_search_scoped_and_preview_compares_identity(monkeypatch,lang):
    c,u,o,x,before=setup(monkeypatch)
    monkeypatch.setattr(m,'current_ui_language',lambda:lang)
    other=m.PacsStudyInbox(orthanc_study_id='33333333-33333333-33333333-33333333-33333333',state='REVIEW_REQUIRED',pacs_patient_name='SYNTHETIC OTHER STUDY')
    m.db.session.add(other);m.db.session.flush()
    body=c.get('/pacs/reconciliation').get_data(as_text=True)
    assert 'manual-study-table' in body and 'manual-selected-study' not in body.split('href=')[0]
    assert 'name="order_id"' not in body
    body=c.get('/pacs/reconciliation',query_string={'study_id':SOURCE,'q':o.accession}).get_data(as_text=True)
    assert 'id="manual-selected-study"' in body
    assert f'name="study_id" value="{SOURCE}"' in body
    assert f'name="study_id" value="{other.orthanc_study_id}"' not in body
    response=c.get('/pacs/reconciliation',query_string={'study_id':SOURCE,'order_id':o.id,'q':o.accession})
    assert response.status_code==200
    body=response.get_data(as_text=True)
    assert 'WRONG' in body and o.accession in body
    assert 'manual-comparison' in body and 'name="preview_token"' in body
    assert body.index('id="manual-selected-study"') < body.index('id="combined-acquisition"')
    assert 'name="identity_confirmed"' in body

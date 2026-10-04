from types import SimpleNamespace as NS
from pathlib import Path
import pytest
import report_template_conversion as conversion
from report_template_library import TemplateError
from test_report_template_library import doc_bytes

class Response:
    def __init__(self,data=None,blob=None):self.data=data;self.blob=blob
    def raise_for_status(self):pass
    def json(self):return self.data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,*args):yield self.blob

def runtime(tmp_path,url='http://documents/cache/files/test/output.docx'):
    calls=[]
    def post(address,**kwargs):
        calls.append((address,kwargs))
        return Response({'endConvert':True,'fileUrl':url})
    m=NS(REPORT_DIR=str(tmp_path),ONLYOFFICE_RIS_INTERNAL_URL='http://ris:8000',ONLYOFFICE_INTERNAL_URL='http://documents',
         _onlyoffice_serializer=lambda:NS(dumps=lambda payload:'scoped-source-token'),_onlyoffice_jwt_encode=lambda payload:'signed-conversion',
         requests=NS(post=post,get=lambda *args,**kwargs:Response(blob=doc_bytes())))
    return m,calls

def test_doc_conversion_uses_trusted_service_and_removes_source(tmp_path):
    m,calls=runtime(tmp_path)
    assert conversion.convert_doc(m,bytes.fromhex('d0cf11e0a1b11ae1')+b'synthetic doc')[:2]==b'PK'
    address,request=calls[0]
    assert address=='http://documents/converter'
    assert request['json']['filetype']=='doc' and request['json']['outputtype']=='docx'
    assert request['json']['url'].startswith('http://ris:8000/api/report-templates/conversion-source/')
    assert request['headers']['Authorization']=='Bearer signed-conversion'
    assert not list(Path(tmp_path).rglob('*.doc'))

@pytest.mark.parametrize('url',['http://evil/cache/files/out.docx','http://documents/not-cache/out.docx','http://documents:1234/cache/files/a','http://user:password@documents/cache/files/a'])
def test_conversion_rejects_foreign_output_and_cleans_up(tmp_path,url):
    m,calls=runtime(tmp_path,url)
    with pytest.raises(TemplateError,match='untrusted'):conversion.convert_doc(m,bytes.fromhex('d0cf11e0a1b11ae1')+b'synthetic')
    assert not list(Path(tmp_path).rglob('*.doc'))

@pytest.mark.parametrize('blob',[b'not a DOC',bytes.fromhex('d0cf11e0a1b11ae1')+b'_VBA_PROJECT'])
def test_invalid_or_macro_doc_never_reaches_converter(tmp_path,blob):
    m,calls=runtime(tmp_path)
    with pytest.raises(TemplateError):conversion.convert_doc(m,blob)
    assert not calls

"""Convert legacy Word templates using the existing internal document server."""
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, quote
from flask import abort, request, send_file
from report_template_library import TemplateError,validate_docx

def convert_doc(m,blob):
    if not blob or len(blob)>5*1024*1024 or not blob.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
        raise TemplateError('Select a valid legacy Word DOC file up to 5 MB.')
    if any(marker in blob.lower() for marker in (b'_vba_project',b'v\x00b\x00a\x00',b'vba/')):
        raise TemplateError('Remove macros from the DOC template before uploading.')
    folder=Path(m.REPORT_DIR)/'_template_conversion';folder.mkdir(parents=True,exist_ok=True)
    source_id=uuid.uuid4().hex;path=folder/(source_id+'.doc')
    with path.open('xb') as out:out.write(blob)
    try:
        token=m._onlyoffice_serializer().dumps({'template_source':source_id})
        payload={'async':False,'filetype':'doc','outputtype':'docx','key':'rb-template-'+source_id,'title':'template.doc',
                 'url':m.ONLYOFFICE_RIS_INTERNAL_URL.rstrip('/')+'/api/report-templates/conversion-source/'+source_id+'?token='+quote(token)}
        jwt=m._onlyoffice_jwt_encode(payload);payload['token']=jwt
        response=m.requests.post(m.ONLYOFFICE_INTERNAL_URL.rstrip('/')+'/converter',json=payload,headers={'Authorization':'Bearer '+jwt},timeout=60)
        response.raise_for_status();result=response.json()
        if result.get('error') or not result.get('endConvert') or not result.get('fileUrl'):raise TemplateError('DOC conversion failed. Save the template as DOCX and upload it again.')
        target=urlsplit(result['fileUrl']);trusted=urlsplit(m.ONLYOFFICE_INTERNAL_URL)
        if (target.scheme,target.hostname,target.port)!=(trusted.scheme,trusted.hostname,trusted.port) or not target.path.startswith('/cache/files/') or target.username or target.password:raise TemplateError('Document conversion returned an untrusted file URL.')
        with m.requests.get(result['fileUrl'],timeout=30,stream=True,allow_redirects=False) as download:
            download.raise_for_status()
            converted=bytearray()
            for chunk in download.iter_content(65536):
                converted.extend(chunk)
                if len(converted)>5*1024*1024:raise TemplateError('Converted DOCX exceeds the 5 MB limit.')
        validate_docx(bytes(converted))
        return bytes(converted)
    except TemplateError:raise
    except Exception:raise TemplateError('Cannot convert DOC now. Upload DOCX or try again later.') from None
    finally:path.unlink(missing_ok=True)

def register_source(m):
    @m.app.get('/api/report-templates/conversion-source/<source_id>')
    def report_template_conversion_source(source_id):
        if not re.fullmatch('[0-9a-f]{32}',source_id):abort(404)
        try:data=m._onlyoffice_serializer().loads(request.args.get('token') or '',max_age=300)
        except Exception:abort(403)
        if data.get('template_source')!=source_id:abort(403)
        path=Path(m.REPORT_DIR)/'_template_conversion'/(source_id+'.doc')
        if not path.is_file() or path.is_symlink():abort(404)
        response=send_file(path,mimetype='application/msword',download_name='template.doc')
        response.headers['Cache-Control']='no-store'
        return response

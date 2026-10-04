"""Reusable DOCX preparation; never replaces an existing clinical document."""
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from docx import Document
from docx.shared import Inches,Pt

PLACEHOLDERS=('PATIENT_NAME','PATIENT_ID','DOB','SEX','ACCESSION','MODALITY','EXAM','STUDY_DATE','REFERRING_DOCTOR','RADIOLOGIST','FINDINGS','IMPRESSION')
CLINICIANS={'RADIOLOGIST','CONSULTANT','RADIOLOGY_CONSULTANT','SUPER_ADMIN','ADMIN'}

class TemplateError(ValueError):pass

def add_heading(doc,text):
    if 'Heading 1' in doc.styles:return doc.add_heading(text,1)
    paragraph=doc.add_paragraph(text)
    paragraph.runs[0].bold=True;paragraph.runs[0].font.size=Pt(14)
    return paragraph

def manager(user):
    return bool(user and user.active and user.role and (user.role.code=='SUPER_ADMIN' or '*' in user.role.permissions() or 'users.manage' in user.role.permissions()))

def clinician(user):
    return bool(user and user.active and user.role and user.role.code in CLINICIANS)

def validate_docx(blob,require_fields=True):
    if not blob or len(blob)>5*1024*1024:raise TemplateError('Upload a DOCX of at most 5 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            entries=z.infolist()
            if len(entries)>500 or sum(x.file_size for x in entries)>30*1024*1024:raise TemplateError('DOCX contents exceed safe limits.')
            names={x.filename for x in entries}
            if len(names)!=len(entries) or not {'[Content_Types].xml','word/document.xml'}.issubset(names):raise TemplateError('Invalid DOCX package.')
            for item in entries:
                name=item.filename.lower()
                if name.startswith('/') or '..' in name.split('/') or '\\' in name or any(x in name for x in ('vbaproject','activex','embeddings/')):raise TemplateError('Macros and embedded objects are not permitted in templates.')
                if name.endswith(('.xml','.rels')):
                    raw=z.read(item)
                    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise TemplateError('Unsafe XML document.')
                    tree=ET.fromstring(raw)
                    if name.endswith('.rels') and any(x.attrib.get('TargetMode')=='External' for x in tree):raise TemplateError('External file and image links are not permitted.')
                    for node in tree.iter():
                        if node.tag.endswith('}instrText') and re.search(r'\b(DDE|DDEAUTO|INCLUDETEXT|INCLUDEPICTURE|LINK)\b',node.text or '',re.I):raise TemplateError('External document fields are not permitted.')
            text=' '.join(x.text or '' for name in names if re.fullmatch(r'word/(document|header\d+|footer\d+)\.xml',name) for x in ET.fromstring(z.read(name)).iter() if x.tag.endswith('}t'))
            # Identity in reusable templates must be patient-independent.
            full=''.join(x.text or '' for name in names if re.fullmatch(r'word/(document|header\d+|footer\d+)\.xml',name) for x in ET.fromstring(z.read(name)).iter() if x.tag.endswith('}t'))
            if require_fields and any('{{'+k+'}}' not in full for k in ('PATIENT_NAME','PATIENT_ID','ACCESSION')):
                raise TemplateError('Use {{PATIENT_NAME}}, {{PATIENT_ID}} and {{ACCESSION}} placeholders. Download the sample template.')
            for marker in re.findall(r'RIS_ACCESSION:\s*(\S+)',text):
                if marker!='{{ACCESSION}}':raise TemplateError('Remove fixed patient accession data from this reusable template.')
        document=Document(io.BytesIO(blob))
        headings={p.text.strip().upper() for p in document.paragraphs}
        if require_fields and not {'FINDINGS','IMPRESSION'}.issubset(headings):raise TemplateError('Keep separate FINDINGS and IMPRESSION headings in the template body.')
    except TemplateError:raise
    except Exception:raise TemplateError('Cannot read this DOCX template.') from None
    return hashlib.sha256(blob).hexdigest()

def normalize_upload(blob):
    """Retain reusable text/layout and add missing identity/report sections."""
    validate_docx(blob,require_fields=False)
    doc=Document(io.BytesIO(blob))
    doc.sections[0].header.add_paragraph('Patient: {{PATIENT_NAME}} | Patient ID: {{PATIENT_ID}} | Accession: {{ACCESSION}}')
    headings={p.text.strip().upper() for p in doc.paragraphs}
    if 'FINDINGS' not in headings:
        heading=add_heading(doc,'FINDINGS')
        doc._element.body.insert(0,heading._p)
    if 'IMPRESSION' not in headings:
        add_heading(doc,'IMPRESSION');doc.add_paragraph('')
    out=io.BytesIO();doc.save(out);result=out.getvalue()
    validate_docx(result)
    return result

def visible(m,t,user,order=None):
    if not t.active:return False
    owner=m.db.session.get(m.User,t.owner_user_id)
    if t.visibility=='PERSONAL':scope=t.owner_user_id==user.id or manager(user)
    elif t.visibility=='DEPARTMENT':scope=bool(owner and user.branch_id and owner.branch_id==user.branch_id and (not order or order.branch_id==user.branch_id)) or manager(user)
    elif t.visibility=='SHARED':scope=True
    else:return False
    if not scope:return False
    def section(modality):return 'XRAY' if str(modality or '').upper() in ('DX','CR','XRAY') else str(modality or '').upper()
    if order and ((t.modality and section(t.modality)!=section(order.modality)) or (t.procedure_id and t.procedure_id!=order.procedure_id)):return False
    return True

def available(m,user,order=None):
    return [t for t in m.DoctorWordTemplate.query.filter_by(active=True).order_by(m.DoctorWordTemplate.created_at.desc()).all() if visible(m,t,user,order)]

def template_bytes(m,t):
    root=(Path(m.REPORT_DIR)/'doctor-templates').resolve()
    raw_path=Path(t.file_path);path=raw_path.resolve()
    if not path.is_relative_to(root) or raw_path.is_symlink() or not path.is_file():raise TemplateError('Template file is unavailable.')
    blob=path.read_bytes();validate_docx(blob);return blob

def paragraphs(container):
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:yield from paragraphs(cell)

def substitute(doc,values):
    containers=[doc]
    seen=set()
    for section in doc.sections:
        for part in (section.header,section.first_page_header,section.even_page_header,section.footer,section.first_page_footer,section.even_page_footer):
            if id(part.part) not in seen:containers.append(part);seen.add(id(part.part))
    for container in containers:
        for p in paragraphs(container):
            runs=list(p.runs);full=''.join(r.text for r in runs)
            offsets=[];pos=0
            for r in runs:offsets.append((pos,pos+len(r.text)));pos+=len(r.text)
            for match in reversed(list(re.finditer(r'\{\{([A-Z_]+)\}\}',full))):
                if match[1] not in values:raise TemplateError('Unsupported placeholder: '+match[1])
                start,end=match.span()
                first=next(i for i,(a,b) in enumerate(offsets) if a<=start<b)
                last=next(i for i,(a,b) in enumerate(offsets) if a<end<=b)
                replacement=str(values[match[1]] or '')
                prefix=runs[first].text[:start-offsets[first][0]]
                suffix=runs[last].text[end-offsets[last][0]:]
                if first==last:runs[first].text=prefix+replacement+suffix
                else:
                    runs[first].text=prefix+replacement
                    for i in range(first+1,last):runs[i].text=''
                    runs[last].text=suffix
    return doc

DEFAULT_HEADER={'title':'RADIOLOGY REPORT','subtitle':'','address':'','phone':'','footer':'','logo_path':'','preserve_template_header':True,'show_dob':True,'show_sex':True,'show_study_date':True,'show_referrer':False}

def header_profile(m,order=None,branch_id=None):
    branch_id=order.branch_id if order else branch_id
    q=m.StudioTemplate.query.filter_by(template_type='REPORT_HEADER',status='PUBLISHED')
    row=q.filter_by(branch_id=branch_id).order_by(m.StudioTemplate.id.desc()).first() if branch_id else None
    if not row:row=q.filter(m.StudioTemplate.branch_id.is_(None)).order_by(m.StudioTemplate.id.desc()).first()
    layout=dict(DEFAULT_HEADER)
    if row:
        try:layout.update(json.loads(row.layout_json))
        except (ValueError,TypeError):raise TemplateError('Published report header is invalid.')
    return layout,row

def values_for(order,report,user):
    p=order.patient
    return {'PATIENT_NAME':p.name,'PATIENT_ID':p.patient_id,'DOB':p.dob or '', 'SEX':p.sex or '',
            'ACCESSION':order.accession,'MODALITY':order.modality,'EXAM':order.procedure,
            'STUDY_DATE':order.scheduled.strftime('%Y-%m-%d %H:%M') if order.scheduled else '',
            'REFERRING_DOCTOR':order.referring_doctor.name if getattr(order,'referring_doctor',None) else '',
            'RADIOLOGIST':report.radiologist or user.full_name or user.username,
            'FINDINGS':report.findings or '', 'IMPRESSION':report.impression or ''}

def apply_header(doc,m,layout,values,uploaded):
    seen=set()
    for section in doc.sections:
        for header in (section.header,section.first_page_header,section.even_page_header):
            if id(header.part) in seen:continue
            seen.add(id(header.part))
            if not uploaded or not layout.get('preserve_template_header'):
                for child in list(header._element):header._element.remove(child)
            if not uploaded or not layout.get('preserve_template_header'):
                logo=layout.get('logo_path')
                if logo:
                    root=(Path(m.REPORT_DIR)/'report-header-assets').resolve();path=Path(logo).resolve()
                    if not path.is_relative_to(root) or not path.is_file():raise TemplateError('Header logo is unavailable.')
                    header.add_paragraph().add_run().add_picture(str(path),width=Inches(1.1))
                p=header.add_paragraph(layout.get('title') or 'RADIOLOGY REPORT');p.runs[0].bold=True;p.runs[0].font.size=Pt(14)
                for k in ('subtitle','address','phone'):
                    if layout.get(k):header.add_paragraph(layout[k])
            width=section.page_width-section.left_margin-section.right_margin
            table=header.add_table(rows=3,cols=2,width=width)
            if 'Table Grid' in doc.styles:table.style='Table Grid'
            for r,(label,value) in zip(table.rows,[('Patient Name',values['PATIENT_NAME']),('Patient ID',values['PATIENT_ID']),('Accession',values['ACCESSION'])]):r.cells[0].text=label;r.cells[1].text=value
            for flag,key,label in [('show_dob','DOB','DOB'),('show_sex','SEX','Sex'),('show_study_date','STUDY_DATE','Study Date'),('show_referrer','REFERRING_DOCTOR','Referring Doctor')]:
                if layout.get(flag):header.add_paragraph(label+': '+values[key])
        if layout.get('footer'):
            for footer in (section.footer,section.first_page_footer,section.even_page_footer):
                if id(footer.part) in seen:continue
                seen.add(id(footer.part));footer.add_paragraph(layout['footer'])

def build(m,order,report,user,template_id=None):
    if template_id:
        t=m.db.session.get(m.DoctorWordTemplate,template_id)
        if not t or not visible(m,t,user,order):raise TemplateError('Template is not available for this doctor or examination.')
        blob=template_bytes(m,t);doc=Document(io.BytesIO(blob));sha=hashlib.sha256(blob).hexdigest()
    else:
        t=None;sha='';doc=Document();doc.add_heading(order.procedure or 'Radiology Report',level=1)
        for title,key in [('FINDINGS','FINDINGS'),('IMPRESSION','IMPRESSION')]:doc.add_heading(title,level=1);doc.add_paragraph('{{'+key+'}}')
        doc.add_paragraph('Radiologist: {{RADIOLOGIST}}')
    values=values_for(order,report,user);substitute(doc,values)
    layout,profile=header_profile(m,order)
    apply_header(doc,m,layout,values,bool(t))
    doc.add_paragraph('RIS_ACCESSION: '+order.accession)
    output=io.BytesIO();doc.save(output)
    return output.getvalue(),{'template_id':t.id if t else None,'template_sha256':sha,'header_profile_id':profile.id if profile else None,'header_version':profile.version_no if profile else 0}

def can_initialize(m,order,report):
    return (str(report.status or 'UNREPORTED').upper() in ('UNREPORTED','DRAFT') and not (report.findings or '').strip() and not (report.impression or '').strip()
            and not m.ReportVersion.query.filter_by(report_id=report.id).first() and not Path(m._onlyoffice_working_path(order)).exists())

def initialize(m,order,report,user,template_id=None):
    order=m.Order.query.filter_by(id=order.id).with_for_update().one()
    report=m.Report.query.filter_by(id=report.id).with_for_update().one()
    path=Path(m._onlyoffice_working_path(order))
    if path.exists():
        if template_id:raise TemplateError('This report already has a working document. Open it without replacing its content.')
        return str(path)
    if not can_initialize(m,order,report):
        if template_id:raise TemplateError('Templates can be selected only before writing starts.')
        return m._onlyoffice_prepare_document(order,report)
    blob,metadata=build(m,order,report,user,template_id)
    # Exclusive creation refuses a concurrent writer; no existing file is replaced.
    try:
        with path.open('xb') as fh:
            try:fh.write(blob)
            except Exception:
                path.unlink(missing_ok=True)
                raise
    except FileExistsError:raise TemplateError('Another editor initialized this report. Reopen the existing document.') from None
    report.status='DRAFT'
    m.audit_as_user(user,'ONLYOFFICE_TEMPLATE_INITIALIZED','order',order.id,json.dumps(dict(metadata,document_sha256=hashlib.sha256(blob).hexdigest())))
    return str(path)

"""Conservative exam-region checks on DICOM metadata, never pixel interpretation."""
import re
import unicodedata

REGIONS = {
    'KNEE': ('KNEE', 'KNEES', 'ركبه', 'ركبة'),
    'CSPINE': ('CSPINE', 'C SPINE', 'CERVICAL SPINE', 'CERVICAL VERTEBRAE', 'فقرات عنقيه', 'فقرات عنقية', 'فقرات رقبيه', 'فقرات رقبية'),
    'LSPINE': ('LSPINE', 'L SPINE', 'LUMBAR SPINE', 'LUMBOSACRAL', 'فقرات قطنيه', 'فقرات قطنية'),
    'TSPINE': ('TSPINE', 'T SPINE', 'THORACIC SPINE', 'فقرات صدريه', 'فقرات صدرية'),
    'HEAD': ('HEAD', 'BRAIN', 'SKULL', 'مخ', 'دماغ', 'راس', 'رأس'),
    'ABDOMEN': ('ABDOMEN', 'ABDOMINAL', 'بطن'),
    'PELVIS': ('PELVIS', 'PELVIC', 'حوض'),
    'CHEST': ('CHEST', 'THORAX', 'صدر'),
    'ANKLE': ('ANKLE', 'كاحل'),
    'SHOULDER': ('SHOULDER', 'كتف'),
    'HIP': ('HIP', 'ورك'),
    'WRIST': ('WRIST', 'رسغ'),
    'ELBOW': ('ELBOW', 'كوع', 'مرفق'),
    'HAND': ('HAND', 'يد'),
    'FOOT': ('FOOT', 'قدم'),
    'NECK': ('NECK', 'رقبه', 'رقبة'),
}


def normalize(value):
    text=''.join(c for c in unicodedata.normalize('NFKC',str(value or '')) if not unicodedata.combining(c))
    return re.sub(r'[^\w]+',' ',text.upper(),flags=re.UNICODE).strip()


def regions_in(value):
    text=' '+normalize(value)+' '
    return {code for code,aliases in REGIONS.items()
            if any(' '+normalize(alias)+' ' in text for alias in aliases)}


def exam_type_match(*,expected_modality,procedure,study_description='',series=(),expected_regions=(),block_unknown=True):
    """Only nonempty acquisition series are evidence; SR/PR/SEG/SC are not acquisitions.

    Any conflicting label blocks, even when another label matches. Missing labels
    must never be presented as confirmed matching. Known DX/CR aliases are allowed.
    """
    expected=set(expected_regions) or regions_in(procedure)
    expected_modality=str(expected_modality or '').upper().strip()
    mod_group={'DX','CR'} if expected_modality in {'DX','CR'} else {expected_modality}
    acquisitions=[s for s in series if int(s.get('instance_count') or 0)>0
                  and str(s.get('modality') or '').upper() not in {'SR','PR','SEG','SC','DOC','KO'}]
    observed=set()
    for s in acquisitions:
        observed |= regions_in(s.get('body_part','')) | regions_in(s.get('description','')) | regions_in(s.get('protocol',''))
    study_regions=regions_in(study_description)
    observed |= study_regions
    modalities={str(s.get('modality') or '').upper().strip() for s in acquisitions if s.get('modality')}
    mismatch_modality=bool(modalities-mod_group)
    mismatch_region=bool(expected and observed-expected)
    unknown=not bool(expected and observed and acquisitions and modalities) or bool(expected-observed)
    status='MISMATCH' if mismatch_modality or mismatch_region else ('REVIEW_REQUIRED' if unknown else 'MATCH')
    return {'status':status,'allowed':status=='MATCH' or (status=='REVIEW_REQUIRED' and not block_unknown),
            'expected_regions':sorted(expected),'observed_regions':sorted(observed),
            'expected_modality':expected_modality,'observed_modalities':sorted(modalities),
            'modality_mismatch':mismatch_modality,'region_mismatch':mismatch_region,
            'unknown':unknown,'metadata_only':True}


def evidence_exam_match(order,evidence,rule=None):
    count,meta,error,series=evidence
    # Existing missing-policy behavior remains a warning, never a claimed MATCH.
    # A configured image policy for a recognized exam requires region evidence.
    modality=getattr(order,'modality','')
    procedure=getattr(order,'procedure','')
    strict=bool(rule and regions_in(procedure))
    result=exam_type_match(expected_modality=modality,procedure=procedure,
        study_description=(meta or {}).get('study_description',''),series=series,
        block_unknown=strict)
    result['policy_defined']=bool(rule)
    result['input']={'modality':modality,'procedure':procedure,
        'study':getattr(order,'pacs_study_id',''),'count':count}
    return result


def cached_exam_gate(order,row):
    import json
    if not row:return True,''
    try:result=json.loads(row.details_json or '{}').get('exam_type')
    except (ValueError,TypeError):return False,'EXAM_METADATA_RECHECK_REQUIRED'
    if not result:return True,''  # Legacy evidence is refreshed by readiness checks.
    current={'modality':order.modality,'procedure':order.procedure,
        'study':order.pacs_study_id,'count':order.pacs_image_count}
    if result.get('input')!=current:return False,'EXAM_METADATA_RECHECK_REQUIRED'
    if not result.get('allowed'):return False,'EXAM_METADATA_'+result.get('status','REVIEW_REQUIRED')
    return True,''

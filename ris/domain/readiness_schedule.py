"""Readiness scheduling configuration and eligibility policies."""
DEFAULTS={'enabled':False,'interval_seconds':300,'XRAY':120,'CT':300,'MR':300,'batch_limit':10}
CLOSED={'FINAL','VERIFIED','CANCELLED'}

def validate_settings(values):
    result={'enabled':values.get('enabled') in (True,'1')}
    for key in ('interval_seconds','XRAY','CT','MR','batch_limit'):
        try:value=int(str(values.get(key,DEFAULTS[key])))
        except (ValueError,TypeError):raise ValueError('Enter whole numbers for intervals and batch size.') from None
        low,high=(1,20) if key=='batch_limit' else (60,3600)
        if not low<=value<=high:raise ValueError(f'{key}: choose a value between {low} and {high}.')
        result[key]=value
    return result


def interval(config,modality):
    modality=str(modality or '').upper()
    if modality in ('DX','CR','XRAY'):modality='XRAY'
    return config.get(modality,config['interval_seconds'])


def eligible(order):
    report=getattr(order,'report',None)
    return (str(order.status or '').upper() not in CLOSED and (not report or str(report.status or '').upper() not in CLOSED)
            and (str(getattr(order,'exam_status','') or '').upper() in ('EXAM_COMPLETED','REPORTING')
                 or str(order.status or '').upper() in ('IMAGES_RECEIVED','EXAM_COMPLETED','REPORTING')))

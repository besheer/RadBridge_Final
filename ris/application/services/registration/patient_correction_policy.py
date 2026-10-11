"""Structured demographic requests; approval records review, not clinical mutation."""
import hashlib,json,re
from datetime import date,datetime
FIELDS={'name':'الاسم / Name','dob':'تاريخ الميلاد / DOB','sex':'النوع / Sex','phone':'الهاتف / Phone','national_id':'الرقم القومي / National ID','address':'العنوان / Address','email':'البريد / Email','nationality':'الجنسية / Nationality'}
IDENTITY_FIELDS={'name','dob','sex'}
def current_value(patient,field):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    if field=='nationality':
        extra=m.PatientDemographicsExtra.query.filter_by(patient_id=patient.id).first()
        return str(extra.nationality or '') if extra else ''
    return str(getattr(patient,field,'') or '')
def patient_orders(patient):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    return m.Order.query.filter_by(patient_id=patient.id).order_by(m.Order.id).all()
def snapshot(patient):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    orders=patient_orders(patient)
    rows=[]
    for o in orders:
        report=o.report
        rows.append([o.id,o.branch_id,o.status,o.exam_status,o.pacs_study_id,o.pacs_image_count,report.status if report else '',report.version if report and hasattr(report,'version') else '',m.ReportVersion.query.filter_by(report_id=report.id).count() if report else 0])
    bookings=[[a.id,a.branch_id,a.status,a.order_id,str(a.scheduled)] for a in m.Appointment.query.filter_by(patient_id=patient.id).order_by(m.Appointment.id).all()]
    data={'values':{f:current_value(patient,f) for f in FIELDS},'estimated':bool(patient.dob_estimated),'orders':rows,'bookings':bookings}
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def impact(patient,field):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    orders=patient_orders(patient)
    return dict(orders=len(orders),visits=m.AssignmentVisit.query.filter_by(patient_id=patient.id).count(),bookings=m.Appointment.query.filter_by(patient_id=patient.id).count(),pacs_orders=sum(bool(o.pacs_study_id) for o in orders),final_reports=sum(bool(o.report and o.report.status=='FINAL') for o in orders),reviewed_reports=sum(bool(o.report and o.report.status=='VERIFIED') for o in orders),branches=len({o.branch_id for o in orders}),identity_change=field in IDENTITY_FIELDS)
def normalize(field,value):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    if field not in FIELDS:raise ValueError('Unsupported patient field')
    value=str(value or '').strip()
    if len(value)>255:raise ValueError('Value is too long / القيمة أطول من المسموح')
    if field=='name' and len(value.split())<3:raise ValueError('Three-part name required / الاسم ثلاثي مطلوب')
    if field=='dob':
        value=value.replace('-','')
        if not re.fullmatch(r'[0-9]{8}',value):raise ValueError('Invalid date of birth')
        try:born=datetime.strptime(value,'%Y%m%d').date()
        except ValueError:raise ValueError('Invalid date of birth')
        if born>date.today():raise ValueError('Date of birth cannot be in the future')
    if field=='sex' and value not in ('M','F','O'):raise ValueError('Select M, F or O')
    if field=='email' and value and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):raise ValueError('Invalid email')
    if any(ord(c)<32 for c in value):raise ValueError('Invalid value')
    rule=m.registration_rule_map().get('patient.'+field)
    ok,msg=m.validate_registration_value(rule,value)
    if not ok:raise ValueError(msg)
    return value
def submit(order,field,value,reason,expected_snapshot):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    patient=order.patient
    value=normalize(field,value);reason=str(reason or '').strip()
    if len(reason)<5:raise ValueError('Correction reason must contain at least 5 characters')
    if current_value(patient,field)==value:raise ValueError('New value must differ / القيمة لم تتغير')
    if snapshot(patient)!=expected_snapshot:raise ValueError('Patient or workflow changed. Reload preview / تغيرت البيانات؛ أعد المعاينة')
    duplicate=m.CorrectionRequest.query.filter(m.CorrectionRequest.order_id==order.id,m.CorrectionRequest.request_type=='WRONG_DEMOGRAPHICS',m.CorrectionRequest.status.in_(m.CORRECTION_OPEN_STATUSES)).first()
    if duplicate:raise ValueError('An active demographic correction request already exists')
    row=m.CorrectionRequest(order_id=order.id,branch_id=order.branch_id,request_type='WRONG_DEMOGRAPHICS',status='NEW',reason=reason[:2000],requested_by=m.current_user().id)
    m.db.session.add(row);m.db.session.flush()
    detail=m.PatientDemographicsCorrection(correction_request_id=row.id,patient_id=patient.id,field_name=field,old_value=current_value(patient,field),proposed_value=value,snapshot_hash=snapshot(patient),impact_json=json.dumps(impact(patient,field)))
    m.db.session.add(detail)
    m.audit('PATIENT_DEMOGRAPHICS_CORRECTION_REQUEST','correction_request',row.id,'Structured field='+field+'; clinical data unchanged')
    return row
def assert_approvable(row):
    from application.legacy_runtime import resolve_runtime as _rb_runtime; m = _rb_runtime()
    detail=row.demographic_detail
    if not detail:m.abort(409,'Legacy request needs a structured replacement before approval')
    patient=m.Patient.query.filter_by(id=detail.patient_id).with_for_update().first_or_404()
    if snapshot(patient)!=detail.snapshot_hash:m.abort(409,'Patient or workflow changed; submit a new preview')
    for order in patient_orders(patient):
        if not m.correction_branch_allowed(order):m.abort(403,'Review across all affected branches is required')
    try:normalize(detail.field_name,detail.proposed_value)
    except ValueError:m.abort(409,'Proposed value no longer meets registration rules')

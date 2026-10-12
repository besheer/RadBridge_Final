"""Role worklist filters; never grant access through saved preferences."""
import json, secrets
from datetime import datetime, timedelta
from flask import request, session, abort
from sqlalchemy import exists, select, or_, and_, func

KEYS = {'q','patient_id','accession','date_from','date_to','priority','modality',
        'device_id','room_key','room_status','exam_status','pacs_status','view',
        'consumables','history','attachments'}

def page_access(m, key):
    if key not in ('TECHNICIAN','NURSING'): return
    user=m.current_user()
    if not user or not user.active or not m.has_perm(key.lower()+'.worklist'): abort(403)
    if request.method=='POST':
        token=session.get('staff_filters_csrf','')
        if not token or not secrets.compare_digest(token,request.form.get('staff_filters_csrf','')): abort(403)

def default_redirect(m,key):
    if request.args: return None
    row=m.SavedSearchFilter.query.filter_by(user_id=m.current_user().id,page_key=key,is_default=True).order_by(m.SavedSearchFilter.id).first()
    if not row:return None
    try:
        values=json.loads(row.filter_json or '{}')
        if not isinstance(values,dict):return None
    except (ValueError,TypeError):return None
    data=m._saved_view_filtered_data(key,values)
    return m.redirect(m.url_for(m.SAVED_VIEW_PAGES[key],_default='1',**data))

def devices_for_user(m):
    user=m.current_user()
    q=m.Device.query
    if not m.has_perm('*'):
        q=q.filter(m.Device.branch_id==user.branch_id) if user.branch_id else q.filter(m.db.false())
    from clinical_scope import read
    scope=read(m,user)
    if scope and scope.get('invalid'):return []
    def permitted(d):
        if not scope:return True
        branch=d.branch.code if d.branch else ''
        return ((not scope['modalities'] or (d.modality or '').upper() in scope['modalities'])
            and (not scope['device_keys'] or (d.id in scope.get('device_ids',[]) and branch+'/'+str(d.ae_title) in scope['device_keys']))
            and (not scope['room_keys'] or branch+'/'+str(d.room) in scope['room_keys']))
    return [d for d in q.order_by(m.Device.branch_id,m.Device.room,m.Device.name).all() if permitted(d)]

def open_now(m,device,now):
    if not device.active or not device.branch or not device.branch.active or (device.operational_status or 'ACTIVE').upper()!='ACTIVE':return False
    try:
        start=datetime.strptime(device.workday_start or '08:00','%H:%M').time()
        end=datetime.strptime(device.workday_end or '22:00','%H:%M').time()
    except ValueError:return False
    t=now.time()
    within=(start<=t<end) if start<end else (t>=start or t<end) if start>end else False
    if not within:return False
    if m.device_booking_reason(device,now,now+timedelta(microseconds=1)):return False
    blocked=m.BookingBlock.query.filter(m.BookingBlock.active.is_(True),
        m.BookingBlock.start_at<=now,m.BookingBlock.end_at>now,
        or_(and_(m.BookingBlock.block_type=='DEVICE',m.BookingBlock.device_id==device.id),
            and_(m.BookingBlock.block_type=='BRANCH',m.BookingBlock.branch_id==device.branch_id))).first()
    return blocked is None

def context(m,key):
    devices=devices_for_user(m)
    session.setdefault('staff_filters_csrf',secrets.token_urlsafe(32))
    now=datetime.now()
    roommap={d.branch.code+'/'+d.room: {'key':d.branch.code+'/'+d.room,'label':d.branch.name+' / '+d.room} for d in devices if d.room and d.branch}
    return dict(staff_devices=devices,staff_rooms=list(roommap.values()),
        staff_modalities=sorted({d.modality for d in devices if d.modality}),
        staff_open_device_ids={d.id for d in devices if open_now(m,d,now)},
        staff_filters_csrf=session['staff_filters_csrf'],staff_filter_keys=sorted(KEYS),
        staff_page_key=key,staff_today=now.strftime('%Y-%m-%d'),
        staff_yesterday=(now-timedelta(days=1)).strftime('%Y-%m-%d'))

def apply(m,q,key,ctx):
    from procedure_staff_workflow import filter_worklist
    q=filter_worklist(m,q,key)
    user=m.current_user()
    if not m.has_perm('*'):
        q=q.filter(m.Order.branch_id==user.branch_id) if user.branch_id else q.filter(m.db.false())
    args=request.args
    for name,column in [('patient_id',m.Patient.patient_id),('accession',m.Order.accession)]:
        value=(args.get(name) or '').strip()
        if value:
            if name=='patient_id':q=q.filter(m.Order.patient.has(m.Patient.patient_id==value))
            else:q=q.filter(column==value)
    for name in ('modality','exam_status','pacs_status'):
        value=(args.get(name) or '').strip().upper()
        if value:q=q.filter(func.upper(getattr(m.Order,name))==value)
    device=args.get('device_id','')
    if device:
        if not device.isdigit():abort(400)
        q=q.filter(m.Order.device_id==int(device))
    room=(args.get('room_key') or '').strip()
    if room:
        q=q.filter(m.Order.device_id.in_([d.id for d in ctx['staff_devices'] if d.branch and d.branch.code+'/'+str(d.room)==room]))
    state=args.get('room_status','')
    if state:
        if state not in ('open_now','closed_now'):abort(400)
        ids=ctx['staff_open_device_ids'] if state=='open_now' else {d.id for d in ctx['staff_devices']}-ctx['staff_open_device_ids']
        q=q.filter(m.Order.device_id.in_(ids))
    for name,model,condition in [
        ('consumables',m.NursingConsumableEntry,m.NursingConsumableEntry.confirmed.is_(True)),
        ('history',m.ClinicalNote,and_(m.ClinicalNote.note_type.in_(('HISTORY','CLINICAL_HISTORY','NURSING_HISTORY')),func.length(func.trim(m.ClinicalNote.text))>0)),
        ('attachments',m.Attachment,m.db.true())]:
        value=args.get(name,'')
        if value:
            if value not in ('present','missing'):abort(400)
            clause=exists(select(model.id).where(model.order_id==m.Order.id,condition).correlate(m.Order))
            q=q.filter(clause if value=='present' else ~clause)
    return q

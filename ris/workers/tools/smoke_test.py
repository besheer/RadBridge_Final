#!/usr/bin/env python3
"""Isolated RIS smoke test.
Runs against a temporary SQLite database and temporary report/attachment folders.
It does NOT touch the production PostgreSQL database.
"""
import os, sys, tempfile, io, traceback
from datetime import datetime, timedelta

TMP=tempfile.mkdtemp(prefix='ris-smoke-')
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(TMP,'ris-smoke.db')
os.environ['REPORT_DIR']=os.path.join(TMP,'reports')
os.environ['ATTACHMENT_DIR']=os.path.join(TMP,'attachments')
os.environ['ORTHANC_URL']='http://127.0.0.1:9'
os.environ['RIS_ADMIN_PASSWORD']='ChangeMe_RIS_Admin_2026'
os.environ['SECRET_KEY']='ris-smoke-secret'

import app as m
m.orthanc_ok=lambda: True
m.send_mwl=lambda order: 'SMOKE_MWL_OK'
app=m.app
app.config.update(TESTING=True)
client=app.test_client()
results=[]

def check(name, response, allowed=(200,201,302,303)):
    ok=response.status_code in allowed
    results.append((name,response.status_code,ok))
    if not ok:
        print(f'FAIL {response.status_code}: {name}')
        try: print(response.get_data(as_text=True)[:2500])
        except Exception: pass
    return response

def safe(name, fn, allowed=(200,201,302,303)):
    try:
        return check(name,fn(),allowed)
    except Exception:
        results.append((name,500,False))
        print('EXCEPTION:',name)
        traceback.print_exc()
        return None

safe('GET login',lambda:client.get('/login'),(200,))
safe('POST login',lambda:client.post('/login',data={'username':'admin','password':'ChangeMe_RIS_Admin_2026'}),(302,))

# Initial page sweep.
for u in ['/', '/patients','/patients/new','/orders','/orders/new','/appointments','/technician','/reports','/analytics',
          '/accounting/receivables','/accounting/reports','/admin','/admin/users','/admin/device-schedules','/admin/devices',
          '/admin/procedures','/admin/contracts','/admin/inventory','/admin/audit','/admin/roles','/admin/branches',
          '/admin/referrers','/admin/import-export']:
    safe('GET '+u,lambda u=u:client.get(u),(200,))

with app.app_context():
    branch=m.Branch.query.first()
    proc=m.Procedure.query.filter_by(modality='CT').first()
    if not proc:
        proc=m.Procedure.query.first()
    branch_id=branch.id
    proc_id=proc.id
    proc_modality=proc.modality
    proc_name=proc.name
    if not m.ReferringDoctor.query.first():
        m.db.session.add(m.ReferringDoctor(code='DRSMOKE',name='Smoke Referrer',specialty='Test'))
        m.db.session.commit()

# Device + schedule.
safe('POST device',lambda:client.post('/admin/devices',data={'branch_id':branch_id,'name':'Smoke CT','modality':proc_modality,'ae_title':'SMOKECT','ip':'127.0.0.1','port':'104','room':'R1','priority':'1'}),(302,))
with app.app_context():
    device=m.Device.query.filter_by(ae_title='SMOKECT').first()
    if not device:
        print('FATAL: Smoke device was not created; stopping dependent tests.')
        sys.exit(1)
    device_id=device.id
safe('POST device schedule',lambda:client.post('/admin/device-schedules',data={'device_id':device_id,'weekday':datetime.now().weekday(),'start_time':'00:00','end_time':'23:59','break_start':'','break_end':''}),(302,))

# Patient.
safe('POST patient',lambda:client.post('/patients/new',data={'name':'Smoke Test Patient','dob':'1990-01-01','sex':'M','phone':'0100000000','national_id':'SMOKENID','address':'Smoke'}),(302,))
with app.app_context():
    patient=m.Patient.query.filter_by(name='Smoke Test Patient').first()
    if not patient:
        print('FATAL: Smoke patient was not created.')
        sys.exit(1)
    patient_id=patient.id
safe('GET order form populated',lambda:client.get(f'/orders/new?patient={patient_id}'),(200,))

# Order + worklist path.
scheduled=(datetime.now()+timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
safe('POST order',lambda:client.post('/orders/new',data={'patient':patient_id,'branch_id':branch_id,'procedure_id':proc_id,'contract_id':'','referring_doctor_id':'','scheduled':scheduled,'approval_no':'','payment_amount':'100','payment_method':'CASH','payment_reference':'SMOKE'}),(302,))
with app.app_context():
    order=m.Order.query.order_by(m.Order.id.desc()).first()
    if not order:
        print('FATAL: Smoke order was not created.')
        sys.exit(1)
    order_id,accession=order.id,order.accession

for u in [f'/orders/{order_id}',f'/reports/{order_id}',f'/reports/{order_id}/word',f'/api/reporting/cases/{accession}','/api/reporting/health']:
    safe('GET '+u,lambda u=u:client.get(u),(200,))

# Attachment upload + download.
safe('POST attachment',lambda:client.post('/attachments/upload',data={'patient_id':str(patient_id),'order_id':str(order_id),'category':'REFERRAL','notes':'Smoke','file':(io.BytesIO(b'%PDF-1.4\nSMOKE\n%%EOF'),'referral.pdf')},content_type='multipart/form-data'),(302,))
with app.app_context():
    att=m.Attachment.query.order_by(m.Attachment.id.desc()).first()
    if not att:
        print('FATAL: Smoke attachment was not created.')
        sys.exit(1)
    att_id=att.id
safe('GET attachment',lambda:client.get(f'/attachments/{att_id}'),(200,))

# Receipts and delivery.
safe('POST receipt payment',lambda:client.post(f'/orders/{order_id}/payment',data={'amount':'50','payment_method':'VISA','reference_no':'POS-SMOKE','notes':'Smoke'}),(302,))
with app.app_context():
    receipt=m.Receipt.query.order_by(m.Receipt.id.desc()).first()
    if not receipt:
        print('FATAL: Smoke receipt was not created.')
        sys.exit(1)
    receipt_id=receipt.id
safe('GET receipt',lambda:client.get(f'/receipts/{receipt_id}'),(200,))
for item in ['REPORT','IMAGES']:
    safe('POST delivery '+item,lambda item=item:client.post(f'/orders/{order_id}/delivery/{item}',data={'delivery_method':'IN_PERSON','recipient_name':'Smoke Patient','recipient_phone':'010'}),(302,))

# Word reporting API: download template, draft, then finalize.
word=client.get(f'/reports/{order_id}/word')
safe('API draft DOCX',lambda:client.post(f'/api/reporting/cases/{accession}/draft',data={'document':(io.BytesIO(word.data),'draft.docx')},content_type='multipart/form-data'),(200,))
safe('API finalize DOCX',lambda:client.post(f'/api/reporting/cases/{accession}/finalize',data={'document':(io.BytesIO(word.data),'final.docx')},content_type='multipart/form-data'),(200,))

# Booking calendar + slot API + actions.
day=datetime.now().date().isoformat()
safe('GET slots',lambda:client.get(f'/api/slots?device_id={device_id}&procedure_id={proc_id}&date={day}'),(200,))
appt_time=(datetime.now()+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
safe('POST appointment',lambda:client.post('/appointments',data={'patient_id':patient_id,'branch_id':branch_id,'procedure_id':proc_id,'device_id':device_id,'scheduled':appt_time,'source':'CALL_CENTER','notes':'Smoke'}),(302,))
with app.app_context():
    appt=m.Appointment.query.order_by(m.Appointment.id.desc()).first()
    if not appt:
        print('FATAL: Smoke appointment was not created.')
        sys.exit(1)
    appt_id=appt.id
safe('GET appointments populated',lambda:client.get('/appointments'),(200,))
safe('POST confirm appointment',lambda:client.post(f'/appointments/{appt_id}/confirm'),(302,))
safe('POST checkin appointment',lambda:client.post(f'/appointments/{appt_id}/checkin'),(302,))

# Contract + price list.
safe('POST contract',lambda:client.post('/admin/contracts',data={'code':'SMOKEC','name':'Smoke Contract','patient_share_percent':'20','discount_percent':'10','approval_required':'1'}),(200,302))
with app.app_context():
    contract=m.Contract.query.filter_by(code='SMOKEC').first()
    if not contract:
        print('FATAL: Smoke contract was not created.')
        sys.exit(1)
    contract_id=contract.id
safe('GET contract prices',lambda:client.get(f'/admin/contracts/{contract_id}/prices'),(200,))
safe('POST contract price',lambda:client.post(f'/admin/contracts/{contract_id}/prices',data={'procedure_id':proc_id,'price':'1234','patient_share_percent':'15'}),(200,302))

# Import/export.
csv_data=b'code,name,name_ar,category,modality,body_part,base_price,duration_min,contrast\nSMOKE-PROC,Smoke Procedure,\xd9\x81\xd8\xad\xd8\xb5 \xd8\xa7\xd8\xae\xd8\xaa\xd8\xa8\xd8\xa7\xd8\xb1,Test,CT,Test,100,20,0\n'
safe('POST procedure import',lambda:client.post('/admin/import-export',data={'entity':'procedures','file':(io.BytesIO(csv_data),'procedures.csv')},content_type='multipart/form-data'),(302,))
for ent in ['procedures','contracts','consumables','devices']:
    safe('GET export '+ent,lambda ent=ent:client.get(f'/admin/export/{ent}.csv'),(200,))

# Final page sweep with populated data.
for u in ['/', '/patients','/orders','/appointments','/technician','/reports','/analytics','/accounting/receivables','/accounting/reports',
          '/admin','/admin/users','/admin/device-schedules','/admin/devices','/admin/procedures','/admin/contracts','/admin/inventory',
          '/admin/audit','/admin/roles','/admin/branches','/admin/referrers','/admin/import-export',f'/orders/{order_id}',f'/reports/{order_id}',f'/admin/devices/{device_id}']:
    safe('FINAL GET '+u,lambda u=u:client.get(u),(200,))

failed=[r for r in results if not r[2]]
print('\nRIS ISOLATED SMOKE TEST')
print('Temporary database:',TMP)
print('Tests:',len(results),'Passed:',len(results)-len(failed),'Failed:',len(failed))
for name,status,ok in results:
    print(('PASS' if ok else 'FAIL'),status,name)
if failed:
    sys.exit(1)
print('\nALL SMOKE TESTS PASSED')

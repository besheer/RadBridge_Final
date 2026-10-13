#!/usr/bin/env python3
import sys, traceback
import app as m
from sqlalchemy import inspect

app=m.app
app.config['TESTING']=False

failed=[]

def result(name, ok, detail=''):
    print(('PASS' if ok else 'FAIL'), name, detail)
    if not ok:
        failed.append(name)

with app.app_context():
    insp=inspect(m.db.engine)
    tables=set(insp.get_table_names())

    for table in ['patient','order','report','report_version','doctor_assignment_profile','case_assignment']:
        result('TABLE '+table, table in tables)

    order_cols={c['name'] for c in insp.get_columns('order')} if 'order' in tables else set()
    for col in ['priority','assigned_doctor_id','assigned_at']:
        result('ORDER COLUMN '+col, col in order_cols)

    result('MODEL assigned_doctor_id',hasattr(m.Order,'assigned_doctor_id'))
    result('MODEL priority',hasattr(m.Order,'priority'))
    result('MODEL assigned_doctor',hasattr(m.Order,'assigned_doctor'))

    try:
        docs=m.assignable_doctors()
        result('ASSIGNABLE DOCTORS QUERY',True,f'count={len(docs)}')
    except Exception as e:
        result('ASSIGNABLE DOCTORS QUERY',False,repr(e))

    admin=(m.User.query.join(m.Role).filter(m.Role.code=='SUPER_ADMIN',m.User.active.is_(True)).first()
           or m.User.query.filter_by(active=True).first())
    first_patient=m.Patient.query.first()
    first_order=m.Order.query.first()

    admin_id=admin.id if admin else None
    patient_id=first_patient.id if first_patient else None
    order_id=first_order.id if first_order else None

client=app.test_client()

# public check
try:
    r=client.get('/login')
    result('GET /login',r.status_code==200,f'status={r.status_code}')
except Exception as e:
    result('GET /login',False,repr(e))

if admin_id:
    with client.session_transaction() as sess:
        sess['uid']=admin_id

    pages=[
        '/',
        '/patients',
        '/patients/new',
        '/orders',
        '/orders/new' + (f'?patient={patient_id}' if patient_id else ''),
        '/appointments',
        '/doctor',
        '/reports',
        '/analytics',
        '/accounting/receivables',
        '/accounting/reports',
        '/admin',
        '/admin/assignment',
        '/assignment/unassigned',
        '/admin/diagnostics',
    ]
    if order_id:
        pages += [f'/orders/{order_id}',f'/reports/{order_id}']

    for url in pages:
        try:
            r=client.get(url)
            result('GET '+url,r.status_code in (200,302),f'status={r.status_code}')
        except Exception:
            result('GET '+url,False)
            traceback.print_exc(limit=3)
else:
    result('ADMIN USER AVAILABLE',False,'No active user')

print()
print('TOTAL FAILURES:',len(failed))
if failed:
    print('FAILED TESTS:')
    for x in failed:
        print(' -',x)
    sys.exit(1)

print('STABILIZATION SELF-TEST PASSED')

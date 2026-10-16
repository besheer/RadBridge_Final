#!/usr/bin/env python3
import sys
import app as m
from sqlalchemy import inspect

required={
  'order':['priority','assigned_doctor_id','assigned_at'],
  'report':['source_path','source_type','verified_by','verified_at','second_verified_by','second_verified_at','finalized_by','addendum_no'],
  'report_version':['source_path','source_type'],
  'appointment':['device_id','checked_in_at','cancelled_at'],
}
with m.app.app_context():
    insp=inspect(m.db.engine)
    tables=set(insp.get_table_names())
    failed=[]
    for table,cols in required.items():
        if table not in tables:
            print('FAIL TABLE',table)
            failed.append(table)
            continue
        actual={c['name'] for c in insp.get_columns(table)}
        for col in cols:
            ok=col in actual
            print(('PASS' if ok else 'FAIL'),table,col)
            if not ok: failed.append(f'{table}.{col}')
    for table in ['doctor_assignment_profile','case_assignment']:
        ok=table in tables
        print(('PASS' if ok else 'FAIL'),'TABLE',table)
        if not ok: failed.append(table)
    if failed:
        print('SCHEMA FAILURES:',','.join(failed))
        sys.exit(1)
print('SCHEMA CHECK PASSED')

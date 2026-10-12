#!/usr/bin/env python3
import os,sys
os.environ.setdefault('TESTING','1')
import app as m
app=m.app
client=app.test_client()
with client:
    checks=[
        ('health','/api/reporting/health',(200,)),
        ('login','/login',(200,)),
    ]
    failed=[]
    for name,url,allowed in checks:
        try:
            r=client.get(url)
            ok=r.status_code in allowed
        except Exception as exc:
            ok=False; r=type('R',(),{'status_code':500})(); print(name,exc)
        print(('PASS' if ok else 'FAIL'),r.status_code,name,url)
        if not ok: failed.append(name)
    if failed:
        sys.exit(1)
print('LIVE SELF-TEST PASSED')

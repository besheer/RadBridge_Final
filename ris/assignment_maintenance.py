"""Minute-level maintenance; no new service container and no report writes."""
import json
import subprocess
import sys
from pathlib import Path
import app as m
from sqlalchemy import text


def main():
    with m.app.app_context(), m.app.test_request_context('/internal/assignment-maintenance'):
        m.db.session.execute(text("SET lock_timeout = '5s'"))
        m.db.session.execute(text("SET statement_timeout = '30s'"))
        touched=m.expire_assignment_offers()
        print(json.dumps({'maintenance':'PASS','expired_offers':len(touched)}))
    # Readiness can be paused independently. A slow PACS must not stall assignment expiry.
    try:
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('readiness_maintenance.py'))],capture_output=True,text=True,timeout=20)
        if result.returncode==0:print(result.stdout.strip())
        else:print(json.dumps({'readiness_maintenance':'ERROR'}))
    except subprocess.TimeoutExpired:
        print(json.dumps({'readiness_maintenance':'TIMEOUT','budget_seconds':20}))


if __name__=='__main__': main()

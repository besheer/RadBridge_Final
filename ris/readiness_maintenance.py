"""Bounded child of the existing minute maintenance job; no new service."""
import json
import app as m
from readiness_operations import run_due

if __name__=='__main__':
    with m.app.app_context():
        print(json.dumps({'readiness_maintenance':run_due(m)}))

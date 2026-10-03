"""Minute-level maintenance; no new service container and no report writes."""
import json
import app as m
from sqlalchemy import text


def main():
    with m.app.app_context(), m.app.test_request_context('/internal/assignment-maintenance'):
        m.db.session.execute(text("SET lock_timeout = '5s'"))
        m.db.session.execute(text("SET statement_timeout = '30s'"))
        touched=m.expire_assignment_offers()
        print(json.dumps({'maintenance':'PASS','expired_offers':len(touched)}))


if __name__=='__main__': main()

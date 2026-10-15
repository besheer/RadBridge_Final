import json

import pytest
import app as m
from test_assignment_distribution import doctor
from test_report_template_routes import isolated


@pytest.fixture(autouse=True)
def rollback_after_test(isolated):
    yield


def signed_in_with_permissions(permissions):
    user=doctor('offer-policy-'+str(len(m.User.query.all())))
    user.role.permissions_json=json.dumps(permissions)
    m.db.session.flush()
    client=m.app.test_client()
    with client.session_transaction() as state:state['uid']=user.id
    return client,user


def test_users_view_can_read_but_cannot_change_global_offer_policy():
    client,_=signed_in_with_permissions(['users.view'])

    assert client.get('/admin/assignment-offers').status_code==200
    assert client.post('/admin/assignment-offers',data={'enabled':'1'}).status_code==403
    assert m.AssignmentOfferPolicy.query.count()==0


def test_users_manage_can_change_global_offer_policy():
    client,user=signed_in_with_permissions(['users.view','users.manage'])

    assert client.post('/admin/assignment-offers',data={'enabled':'1'}).status_code==302
    policy=m.AssignmentOfferPolicy.query.one()
    assert policy.enabled and policy.updated_by==user.id

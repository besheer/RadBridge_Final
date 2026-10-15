import json
import uuid

import pytest
import app as m
from test_assignment_distribution import doctor


@pytest.fixture(autouse=True)
def isolated(app_ctx, monkeypatch):
    monkeypatch.setattr(m.db.session, 'commit', m.db.session.flush)
    yield
    m.db.session.rollback()
    m.db.session.remove()


def sign_in(permissions):
    user=doctor('admin-comm-'+uuid.uuid4().hex[:8])
    user.role.permissions_json=json.dumps(permissions)
    m.db.session.flush()
    client=m.app.test_client()
    with client.session_transaction() as state:state['uid']=user.id
    return client,user


def test_users_view_can_read_but_cannot_change_communications():
    client,_=sign_in(['users.view'])

    assert client.get('/admin/communications').status_code==200
    assert client.post('/admin/communications',data={'channel':'EMAIL','enabled':'1'}).status_code==403
    assert client.post('/admin/communication-templates',data={'code':'SYNTHETIC'}).status_code==403
    assert m.CommunicationTemplate.query.count()==0


def test_users_manage_can_change_communications_and_templates():
    client,user=sign_in(['users.view','users.manage'])
    channel=m.CommunicationChannelSetting(channel='EMAIL',enabled=False)
    m.db.session.add(channel);m.db.session.flush()

    assert client.post('/admin/communications',data={'channel':'EMAIL','enabled':'1','provider':'SYNTHETIC'}).status_code==302
    assert channel.enabled and channel.provider=='SYNTHETIC'
    assert client.post('/admin/communication-templates',data={'code':'SYNTHETIC','name_en':'Synthetic template','body_template':'Synthetic body'}).status_code==302
    template=m.CommunicationTemplate.query.filter_by(code='SYNTHETIC').one()
    assert template.created_by==user.id

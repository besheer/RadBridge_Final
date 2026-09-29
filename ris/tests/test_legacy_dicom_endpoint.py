"""Legacy endpoint changes never alter incoming DICOM permissions."""
import uuid
from unittest.mock import Mock

import pytest


FIELDS = {
    'Host': '172.18.0.1', 'Port': 5108,
    'AllowEcho': True, 'AllowEventReport': False,
    'AllowFind': False, 'AllowFindWorklist': True,
    'AllowGet': False, 'AllowMove': False, 'AllowNAction': False,
    'AllowStore': True, 'AllowTranscoding': True,
    'LocalAet': 'RISPACS', 'Manufacturer': 'Generic',
    'RetrieveMethod': 'C-MOVE', 'Timeout': 10, 'UseDicomTls': False,
}


def response(data):
    result = Mock()
    result.json.return_value = data
    return result


def setup_node(m):
    ae = 'LEGACY_' + uuid.uuid4().hex[:8].upper()
    row = m.DiscoveredDicomNode(ae_title=ae, host='197.35.52.171',
                                status='APPROVED', port=0, node_type='MODALITY')
    m.db.session.add(row)
    m.db.session.commit()
    return row, dict(FIELDS, AET=ae)


def test_legacy_edit_updates_endpoint_and_preserves_permissions(app_ctx, monkeypatch):
    m = app_ctx
    row, old = setup_node(m)
    updated = dict(old, Host='197.35.52.171', Port=5109)
    get = Mock(side_effect=[response({row.ae_title: old}), response(updated)])
    put = Mock(return_value=response({}))
    monkeypatch.setattr(m.requests, 'get', get)
    monkeypatch.setattr(m.requests, 'put', put)
    with m.app.test_request_context(
        '/admin/pacs/discovery/%s/legacy-endpoint' % row.id,
        method='POST', data={'expected_host': old['Host'],
                             'expected_port': old['Port'],
                             'host': updated['Host'], 'port': updated['Port']}
    ):
        result = m.pacs_discovery_legacy_endpoint.__wrapped__(row.id)
        assert result.status_code == 302
    assert put.call_count == 1
    assert put.call_args.kwargs['json'] == updated
    assert m.db.session.get(m.DiscoveredDicomNode, row.id).port == 5109
    assert m.AuditLog.query.filter_by(action='DICOM_LEGACY_ENDPOINT_EDIT',
                                      entity_id=str(row.id)).count() == 1


def test_legacy_edit_rolls_back_if_orthanc_changes_permissions(app_ctx, monkeypatch):
    m = app_ctx
    row, old = setup_node(m)
    updated = dict(old, Host='197.35.52.171', Port=5109)
    unexpected = dict(updated, AllowStore=False)
    get = Mock(side_effect=[response({row.ae_title: old}),
                            response(unexpected), response(old)])
    put = Mock(return_value=response({}))
    monkeypatch.setattr(m.requests, 'get', get)
    monkeypatch.setattr(m.requests, 'put', put)
    with m.app.test_request_context(
        '/admin/pacs/discovery/%s/legacy-endpoint' % row.id,
        method='POST', data={'expected_host': old['Host'],
                             'expected_port': old['Port'],
                             'host': updated['Host'], 'port': updated['Port']}
    ):
        with pytest.raises(RuntimeError):
            m.pacs_discovery_legacy_endpoint.__wrapped__(row.id)
    assert [call.kwargs['json'] for call in put.call_args_list] == [updated, old]
    assert m.db.session.get(m.DiscoveredDicomNode, row.id).port == 0
    assert m.AuditLog.query.filter_by(action='DICOM_LEGACY_ENDPOINT_EDIT',
                                      entity_id=str(row.id)).count() == 0

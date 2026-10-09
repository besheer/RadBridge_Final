import json
import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dicom_node_control import (policy_ready, node_payload, modality_key,
                                delete_modality, legacy_endpoint_payload,
                                legacy_endpoint_matches)
from unittest.mock import Mock


class DicomNodeControlTests(unittest.TestCase):
    def test_permissive_and_missing_policy_fail_closed(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'orthanc.json'
            self.assertFalse(policy_ready(str(path)))
            config = {
                'DicomCheckModalityHost': False,
                'DicomAlwaysAllowEcho': False,
                'DicomAlwaysAllowStore': True,
                'DicomAlwaysAllowFind': False,
                'DicomAlwaysAllowFindWorklist': False,
                'DicomAlwaysAllowGet': False,
                'DicomAlwaysAllowMove': False,
                'DicomModalitiesInDatabase': True,
            }
            path.write_text(json.dumps(config))
            self.assertFalse(policy_ready(str(path)))
            config['DicomCheckModalityHost'] = True
            config['DicomAlwaysAllowStore'] = False
            path.write_text(json.dumps(config))
            self.assertTrue(policy_ready(str(path)))

    def test_node_registration_grants_only_selected_operations(self):
        node = node_payload('radbridge_mr', '197.35.52.171', 5108, allow_find=True)
        self.assertEqual(node, {
            'AET': 'RADBRIDGE_MR', 'Host': '197.35.52.171', 'Port': 5108,
            'AllowEcho': True, 'AllowFind': False, 'AllowFindWorklist': True,
            'AllowStore': False,
            'AllowMove': False, 'AllowGet': False,
        })
        store_only = node_payload('radbridge_mr', '197.35.52.171', 5108,
                                  allow_store=True)
        self.assertFalse(store_only['AllowFind'])
        self.assertFalse(store_only['AllowFindWorklist'])
        self.assertEqual(modality_key(12), 'rb-ingress-12')

    def test_worklist_and_store_never_grant_study_find(self):
        node = node_payload('RADBRIDGE_MR', '197.35.52.171', 5108,
                            allow_find=True, allow_store=True)
        self.assertTrue(node['AllowFindWorklist'])
        self.assertTrue(node['AllowStore'])
        self.assertFalse(node['AllowFind'])
        self.assertFalse(node['AllowMove'])
        self.assertFalse(node['AllowGet'])

    def test_invalid_identity_is_rejected(self):
        for ae, host, port in (
            ('A' * 17, '197.35.52.171', 5108),
            ('RADBRIDGE_MR', 'example.org', 5108),
            ('RADBRIDGE_MR', '197.35.52.171', 0),
            ('RADBRIDGE_MR', '197.35.52.171', 65536),
        ):
            with self.subTest(ae=ae, host=host, port=port):
                with self.assertRaises(ValueError):
                    node_payload(ae, host, port, allow_store=True)

    def test_no_permission_is_rejected(self):
        with self.assertRaises(ValueError):
            node_payload('RADBRIDGE_MR', '197.35.52.171', 5108)

    def test_disable_targets_only_modality_endpoint(self):
        url = 'http://orthanc:8042/modalities/rb-ingress-12'
        client = Mock()
        delete_modality(url, ('user', 'password'), client)
        client.delete.assert_called_once_with(
            url, auth=('user', 'password'), timeout=10)
        client.delete.return_value.raise_for_status.assert_called_once_with()

    def test_legacy_endpoint_edit_preserves_all_permissions_and_options(self):
        original = {
            'AET': 'RADBRIDGE_MR', 'Host': '172.18.0.1', 'Port': 5108,
            'AllowEcho': True, 'AllowEventReport': False,
            'AllowFind': False, 'AllowFindWorklist': True,
            'AllowGet': False, 'AllowMove': False, 'AllowNAction': False,
            'AllowStore': True, 'AllowTranscoding': True,
            'LocalAet': 'RISPACS', 'Manufacturer': 'Generic',
            'RetrieveMethod': 'C-MOVE', 'Timeout': 10, 'UseDicomTls': False,
        }
        edited = legacy_endpoint_payload(original, '197.35.52.171', '5108')
        self.assertEqual(original['Host'], '172.18.0.1')
        self.assertEqual(edited['Host'], '197.35.52.171')
        self.assertTrue(legacy_endpoint_matches(original, edited, edited))
        changed_permission = dict(edited, AllowStore=False)
        self.assertFalse(legacy_endpoint_matches(original, changed_permission, edited))
        for bad in ('example.com', '999.999.999.999'):
            with self.assertRaises(ValueError):
                legacy_endpoint_payload(original, bad, 5108)
        with self.assertRaises(ValueError):
            legacy_endpoint_payload(dict(original, FutureAccessFlag=True),
                                    '197.35.52.171', 5108)

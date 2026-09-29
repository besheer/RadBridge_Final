import json
import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dicom_node_control import policy_ready, node_payload, modality_key, delete_modality
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
            'AllowEcho': True, 'AllowFind': True, 'AllowFindWorklist': True,
            'AllowStore': False,
            'AllowMove': False, 'AllowGet': False,
        })
        store_only = node_payload('radbridge_mr', '197.35.52.171', 5108,
                                  allow_store=True)
        self.assertFalse(store_only['AllowFind'])
        self.assertFalse(store_only['AllowFindWorklist'])
        self.assertEqual(modality_key(12), 'rb-ingress-12')

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

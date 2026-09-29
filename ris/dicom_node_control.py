"""Fail-closed Orthanc ingress registration for the DICOM node admin page.

The policy file must be the running Orthanc configuration, mounted read-only
into RIS. Deployment must verify the shared file and restart contract before
setting RADBRIDGE_ORTHANC_POLICY_FILE. A missing or permissive policy disables
all ingress mutations.
"""

import ipaddress
import json
import os
import re


REQUIRED_POLICY = {
    'DicomCheckModalityHost': True,
    'DicomAlwaysAllowEcho': False,
    'DicomAlwaysAllowStore': False,
    'DicomAlwaysAllowFind': False,
    'DicomAlwaysAllowFindWorklist': False,
    'DicomAlwaysAllowGet': False,
    'DicomAlwaysAllowMove': False,
    'DicomModalitiesInDatabase': True,
}


def policy_ready(path=None):
    path = path or os.environ.get('RADBRIDGE_ORTHANC_POLICY_FILE', '')
    if not path:
        return False
    try:
        with open(path, encoding='utf-8') as stream:
            config = json.load(stream)
    except (OSError, ValueError):
        return False
    return all(config.get(key) is value for key, value in REQUIRED_POLICY.items())


def node_payload(ae, host, port, *, allow_find=False, allow_store=False):
    ae = str(ae or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9_ -]{1,16}', ae):
        raise ValueError('AE Title must contain 1–16 DICOM-compatible characters')
    try:
        host = str(ipaddress.ip_address(str(host or '').strip()))
        port = int(port)
    except (ValueError, TypeError):
        raise ValueError('A numeric source IP and listener port are required') from None
    if not 1 <= port <= 65535:
        raise ValueError('Listener port is outside 1–65535')
    if not (allow_find or allow_store):
        raise ValueError('Select at least one incoming permission')
    return {
        'AET': ae, 'Host': host, 'Port': port,
        # MWL queries have their own permission. Do not expose patient/study C-FIND.
        'AllowEcho': True, 'AllowFind': False,
        'AllowFindWorklist': bool(allow_find),
        'AllowStore': bool(allow_store), 'AllowMove': False, 'AllowGet': False,
    }


def modality_key(node_id):
    return f'rb-ingress-{int(node_id)}'


LEGACY_MODALITY_FIELDS = frozenset({
    'AET', 'Host', 'Port', 'AllowEcho', 'AllowEventReport', 'AllowFind',
    'AllowFindWorklist', 'AllowGet', 'AllowMove', 'AllowNAction',
    'AllowStore', 'AllowTranscoding', 'LocalAet', 'Manufacturer',
    'RetrieveMethod', 'Timeout', 'UseDicomTls',
})


def legacy_endpoint_payload(current, host, port):
    """Change only a legacy modality endpoint, preserving every access flag."""
    if not isinstance(current, dict) or set(current) != LEGACY_MODALITY_FIELDS:
        raise ValueError('Unreviewed Orthanc modality fields')
    ae = current.get('AET')
    if not isinstance(ae, str) or not re.fullmatch(r'[A-Z0-9_ -]{1,16}', ae):
        raise ValueError('Invalid legacy AE Title')
    # Reuse the strict numeric source IP and listener port validation.
    validated = node_payload(ae, host, port, allow_find=True)
    payload = current.copy()
    payload['Host'] = validated['Host']
    payload['Port'] = validated['Port']
    return payload


def legacy_endpoint_matches(before, after, proposed):
    """Orthanc must retain all fields other than the requested endpoint."""
    return (isinstance(after, dict) and isinstance(before, dict) and
            isinstance(proposed, dict) and
            after == proposed and
            all(proposed.get(key) == value for key, value in before.items()
                if key not in ('Host', 'Port')))


def delete_modality(url, auth, client):
    """Delete a registration, never a DICOM resource."""
    response = client.delete(url, auth=auth, timeout=10)
    response.raise_for_status()

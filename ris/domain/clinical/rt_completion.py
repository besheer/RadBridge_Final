"""Manual session completion fingerprint; no prescribed-dose calculation."""
import hashlib
import json


def fingerprint(actual, reference, variance_reason):
    return hashlib.sha256(json.dumps([
        format(actual.normalize(),'f'),reference,variance_reason]).encode()).hexdigest()

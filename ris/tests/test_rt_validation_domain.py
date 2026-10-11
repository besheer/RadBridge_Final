from datetime import datetime
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import radiotherapy as legacy
from domain.clinical import rt_validation as policy


def test_legacy_helpers_are_the_same_domain_functions():
    assert legacy.amount is policy.amount
    assert legacy.text is policy.text
    assert legacy.local_time is policy.local_time
    assert policy.amount('1.000001')==Decimal('1.000001')
    assert policy.local_time('2026-01-01T13:00:00+03:00')==datetime(2026,1,1,10)


def test_validation_import_needs_no_web_database_or_runtime():
    root=str(Path(__file__).resolve().parents[1])
    code="import sys;sys.path.insert(0,%r);import domain.clinical.rt_validation;assert not any(n=='flask' or n=='sqlalchemy' or n.startswith('infrastructure.') or n=='application.legacy_runtime' for n in sys.modules)" % root
    subprocess.run([sys.executable,'-c',code],check=True)

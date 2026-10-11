"""Compatibility alias to the report writer composition edge."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.report_transaction_writer')

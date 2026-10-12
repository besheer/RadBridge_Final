"""Compatibility alias to insurance authorization/readiness composition."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.insurance_policy')

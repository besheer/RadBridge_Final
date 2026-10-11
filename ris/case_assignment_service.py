"""Compatibility alias for legacy transaction entry points."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.case_assignment_service')

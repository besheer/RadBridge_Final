"""Compatibility entry point for web.compatibility.assignment_monitor."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.assignment_monitor')

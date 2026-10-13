"""Compatibility entry point for web.extensions.staff_worklist_filters."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.staff_worklist_filters')

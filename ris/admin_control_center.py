"""Compatibility entry point for web.extensions.admin_control_center."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.admin_control_center')

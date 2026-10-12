"""Compatibility entry point for web.compatibility.user_access_policy."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.user_access_policy')

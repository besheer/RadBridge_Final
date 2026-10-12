"""Compatibility entry point for web.extensions.radiotherapy."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.radiotherapy')

"""Compatibility entry point for web.compatibility.legacy_booking."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.legacy_booking')

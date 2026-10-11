"""Compatibility entry point for infrastructure.adapters.registration.radbridge_ocr."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('infrastructure.adapters.registration.radbridge_ocr')

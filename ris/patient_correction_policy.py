"""Compatibility entry point for web.compatibility.patient_correction_policy."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.patient_correction_policy')

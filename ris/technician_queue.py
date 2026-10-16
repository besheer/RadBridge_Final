"""Compatibility entry point for application.services.clinical.technician_queue."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('application.services.clinical.technician_queue')

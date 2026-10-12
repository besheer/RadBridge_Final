"""Compatibility entry point for infrastructure.adapters.reporting.report_storage_safety."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('infrastructure.adapters.reporting.report_storage_safety')

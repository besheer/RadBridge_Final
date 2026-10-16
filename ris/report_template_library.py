"""Compatibility entry point for application.services.reporting.report_template_library."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('application.services.reporting.report_template_library')

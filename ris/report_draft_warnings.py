"""Compatibility entry point for web.extensions.report_draft_warnings."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.report_draft_warnings')

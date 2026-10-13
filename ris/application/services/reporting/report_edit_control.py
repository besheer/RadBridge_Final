"""Compatibility alias to report edit lease composition."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.report_edit_control')

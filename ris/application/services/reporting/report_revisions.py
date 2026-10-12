"""Compatibility alias to correction HTTP/evidence composition."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.report_revisions')

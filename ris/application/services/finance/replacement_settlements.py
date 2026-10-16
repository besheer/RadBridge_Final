"""Compatibility alias to settlement HTTP/authorization composition."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.replacement_settlements')

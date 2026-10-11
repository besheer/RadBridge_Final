"""Compatibility alias for scoped web registration and legacy entry points."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.clinical_scope')

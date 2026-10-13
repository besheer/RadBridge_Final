"""Compatibility alias for grouped visit entry points."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.compatibility.assignment_visit_grouping')

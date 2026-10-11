"""Compatibility entry point for application.services.assignment.assignment_distribution."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('application.services.assignment.assignment_distribution')

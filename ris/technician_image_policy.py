"""Compatibility import; canonical implementation: domain.clinical.images."""
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("domain.clinical.images")

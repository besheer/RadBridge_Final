"""Compatibility import; canonical implementation: domain.imaging.resolution."""
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("domain.imaging.resolution")

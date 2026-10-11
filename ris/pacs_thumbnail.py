"""Compatibility entry point for infrastructure.adapters.imaging.pacs_thumbnail."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('infrastructure.adapters.imaging.pacs_thumbnail')

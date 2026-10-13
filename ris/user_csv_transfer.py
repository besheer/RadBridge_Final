"""Compatibility entry point for web.extensions.user_csv_transfer."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.user_csv_transfer')

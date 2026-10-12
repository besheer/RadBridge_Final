"""Compatibility entry point for web.extensions.dicom_export_routes."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('web.extensions.dicom_export_routes')

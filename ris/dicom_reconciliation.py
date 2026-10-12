"""Compatibility entry point for application.services.imaging.dicom_reconciliation."""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('application.services.imaging.dicom_reconciliation')

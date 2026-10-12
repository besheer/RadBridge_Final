"""Compatibility entry point for workers.readiness_maintenance."""
import importlib as _importlib
import sys as _sys
if __name__ == "__main__":
    import runpy as _runpy
    _runpy.run_module('workers.readiness_maintenance', run_name="__main__")
else:
    _sys.modules[__name__] = _importlib.import_module('workers.readiness_maintenance')

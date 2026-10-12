"""Compatibility entry point for workers.backup_worker."""
import importlib as _importlib
import sys as _sys
if __name__ == "__main__":
    import runpy as _runpy
    _runpy.run_module('workers.backup_worker', run_name="__main__")
else:
    _sys.modules[__name__] = _importlib.import_module('workers.backup_worker')

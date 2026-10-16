"""Compatibility entry point for workers.tools.bootstrap_db."""
import importlib as _importlib
import sys as _sys
if __name__ == "__main__":
    import runpy as _runpy
    _runpy.run_module('workers.tools.bootstrap_db', run_name="__main__")
else:
    _sys.modules[__name__] = _importlib.import_module('workers.tools.bootstrap_db')

"""Compatibility entry point for workers.tools.schema_check."""
import importlib as _importlib
import sys as _sys
if __name__ == "__main__":
    import runpy as _runpy
    _runpy.run_module('workers.tools.schema_check', run_name="__main__")
else:
    _sys.modules[__name__] = _importlib.import_module('workers.tools.schema_check')

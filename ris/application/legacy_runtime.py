"""Single explicit seam for services still coupled to legacy composition.

New services should receive narrow dependencies. This resolver preserves the
existing one-clinical-application-per-process contract without eager imports.
"""
import importlib
import sys


def resolve_runtime():
    module = sys.modules.get('app')
    return module if module is not None else importlib.import_module('app')

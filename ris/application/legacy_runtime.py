"""Single explicit seam for services still coupled to legacy composition.

New services should receive narrow dependencies. This resolver selects the
construction/request runtime without eagerly importing the legacy entry point.
"""
import importlib
import sys
from contextvars import ContextVar

BUILD_RUNTIME = ContextVar('radbridge_build_runtime', default=None)


def resolve_runtime():
    building = BUILD_RUNTIME.get()
    if building is not None:
        return building
    from flask import current_app, has_app_context
    if has_app_context():
        runtime = current_app.extensions.get('radbridge_runtime')
        if runtime is not None:
            return runtime
    module = sys.modules.get('app')
    return module if module is not None else importlib.import_module('app')

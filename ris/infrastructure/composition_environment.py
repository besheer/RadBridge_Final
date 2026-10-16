"""Construction-scoped configuration without changing process environment."""
from contextvars import ContextVar
import os as _os
from types import MappingProxyType

BUILD_ENVIRONMENT = ContextVar('radbridge_build_environment', default=None)


class BoundOS:
    """Keep filesystem operations while binding composition reads to a snapshot."""
    def __init__(self, environment):
        self.environ = MappingProxyType(dict(environment))

    def getenv(self, key, default=None):
        return self.environ.get(key, default)

    def __getattr__(self, name):
        return getattr(_os, name)


def composition_os():
    environment = BUILD_ENVIRONMENT.get()
    return _os if environment is None else BoundOS(environment)

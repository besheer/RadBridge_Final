"""Explicit compatibility bindings for legacy orchestration dependencies.

Bindings retain live object identity and test overrides. They are not a security
boundary: role, branch and clinical authorization remain in the handlers/policies.
"""


class Bindings:
    __slots__ = ("_target", "_allowed")

    def __init__(self, target, allowed):
        self._target = target
        self._allowed = frozenset(allowed)

    def __getattr__(self, name):
        if name not in self._allowed:
            raise AttributeError("Undeclared component dependency: " + name)
        return getattr(self._target, name)

    def namespace(self):
        """Expose only declared bindings to legacy dynamic existence checks."""
        target = vars(self._target)
        return {name: target[name] for name in self._allowed if name in target}

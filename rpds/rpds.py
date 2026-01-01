"""
Minimal pure-Python shim for the `rpds` package used by `referencing`/`jsonschema`.

This provides lightweight stand-ins for the small API surface the library imports
so tests can run on platforms where a binary wheel is not available (e.g., Python 3.14
on Windows). These classes are intentionally minimal — they implement basic
container behaviour and are sufficient for import-time usage in our test suite.
"""
from collections import UserDict, UserList


class HashTrieMap(dict):
    """Minimal mapping shim with a `convert` classmethod expected by `referencing`.

    The real `rpds.HashTrieMap` provides persistent-map behaviour; for our
    test-suite we only need a mutable mapping that exposes a `convert` helper
    to construct a HashTrieMap from various inputs.
    """

    @classmethod
    def convert(cls, obj=None):
        if obj is None:
            return cls()
        if isinstance(obj, cls):
            return obj
        # If it's a mapping, copy its dict
        if hasattr(obj, "items"):
            return cls(dict(obj.items()))
        # Otherwise try to consume as iterable of pairs
        try:
            return cls(dict(obj))
        except Exception:
            # Fallback: return empty map
            return cls()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        return self


class HashTrieSet(set):
    """Minimal set shim with a `convert` classmethod used by `referencing`."""

    @classmethod
    def convert(cls, obj=None):
        if obj is None:
            return cls()
        if isinstance(obj, cls):
            return obj
        try:
            return cls(obj)
        except Exception:
            return cls()

    def add(self, *args, **kwargs):
        return super().add(*args, **kwargs)


class List(list):
    """Minimal list shim with a `convert` classmethod for compatibility."""

    @classmethod
    def convert(cls, obj=None):
        if obj is None:
            return cls()
        if isinstance(obj, cls):
            return obj
        try:
            return cls(obj)
        except Exception:
            return cls()


__all__ = ["HashTrieMap", "HashTrieSet", "List"]

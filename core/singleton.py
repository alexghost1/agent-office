"""Singleton registry — una instancia por agente en todo el proceso."""
from __future__ import annotations
import threading

_registry: dict[str, object] = {}
_lock = threading.Lock()

def get_or_create(key: str, factory):
    """Returns existing instance or creates one via factory()."""
    if key not in _registry:
        with _lock:
            if key not in _registry:
                _registry[key] = factory()
    return _registry[key]

def clear(key: str = None):
    """For testing only."""
    global _registry
    with _lock:
        if key:
            _registry.pop(key, None)
        else:
            _registry.clear()

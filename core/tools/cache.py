"""
Caché inteligente con TTL para APIs externas
Evita rate limits y reduce latencia
"""
import os
import json
import time
import hashlib
import threading
from pathlib import Path
from loguru import logger

CACHE_DIR = Path(os.getenv("LOGS_DIR", Path(__file__).parent.parent.parent / "data" / "logs")) / "cache"
DEFAULT_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))


class Cache:
    def __init__(self, ttl: int = DEFAULT_TTL):
        self.ttl = ttl
        self._memory = {}
        self._lock = threading.RLock()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _key(self, *args, **kwargs) -> str:
        raw = json.dumps([args, kwargs], sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def get(self, key: str = None, **kwargs):
        if key is None and kwargs:
            key = self._key(kwargs)
        if key is None:
            return None
        with self._lock:
            entry = self._memory.get(key)
            if entry and time.time() < entry["expires"]:
                return entry["value"]
        path = self._path(key)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                if time.time() < data["expires"]:
                    with self._lock:
                        self._memory[key] = data
                    return data["value"]
                path.unlink(missing_ok=True)
            except Exception:
                path.unlink(missing_ok=True)
        return None

    def set(self, key: str, value, ttl: int = None):
        expires = time.time() + (ttl or self.ttl)
        entry = {"expires": expires, "value": value, "created": time.time()}
        with self._lock:
            self._memory[key] = entry
        try:
            self._path(key).write_text(json.dumps(entry, default=str))
        except Exception:
            pass

    def make_key(self, *args, **kwargs) -> str:
        return self._key(*args, **kwargs)

    def memoize(self, ttl: int = None):
        def decorator(fn):
            def wrapper(*args, **kwargs):
                key = self.make_key(*args, **kwargs)
                cached = self.get(key=key)
                if cached is not None:
                    return cached
                result = fn(*args, **kwargs)
                self.set(key, result, ttl=ttl)
                return result
            return wrapper
        return decorator

    def invalidate(self, key: str = None, **kwargs):
        if key is None and kwargs:
            key = self.make_key(**kwargs)
        if key:
            with self._lock:
                self._memory.pop(key, None)
            self._path(key).unlink(missing_ok=True)

    def clear(self):
        with self._lock:
            self._memory.clear()
        for p in CACHE_DIR.glob("*.json"):
            p.unlink(missing_ok=True)
        logger.info("Caché limpiada")

    def stats(self) -> dict:
        with self._lock:
            mem = len(self._memory)
        files = len(list(CACHE_DIR.glob("*.json")))
        return {"memory_entries": mem, "disk_files": files, "ttl": self.ttl}


cache = Cache()

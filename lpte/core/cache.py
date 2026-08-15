"""
Thread-safe LRU cache for ClassificationResult objects.

Avoids re-analyzing identical text+language+threshold combinations.
Pure Python — no external dependencies.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Generic, Hashable, Optional, TypeVar

_KT = TypeVar("_KT", bound=Hashable)
_VT = TypeVar("_VT")


class LRUCache(Generic[_KT, _VT]):
    """
    Thread-safe Least-Recently-Used cache with bounded capacity.

    Args:
        capacity: Maximum number of entries to hold. When exceeded,
                  the least recently used entry is evicted. Default 512.
    """

    def __init__(self, capacity: int = 512) -> None:
        if capacity < 1:
            raise ValueError(f"LRUCache capacity must be >= 1, got {capacity}")
        self._capacity = capacity
        self._store: OrderedDict[_KT, _VT] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: _KT) -> Optional[_VT]:
        """Return cached value or None if not present. Marks key as recently used."""
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return self._store[key]

    def put(self, key: _KT, value: _VT) -> None:
        """Insert or update a cache entry. Evicts LRU entry if over capacity."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = value
            if len(self._store) > self._capacity:
                self._store.popitem(last=False)  # remove oldest

    def invalidate(self, key: _KT) -> bool:
        """Remove a specific key. Returns True if key was present."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Evict all entries and reset statistics."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        with self._lock:
            return len(self._store)

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def hits(self) -> int:
        with self._lock:
            return self._hits

    @property
    def misses(self) -> int:
        with self._lock:
            return self._misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a fraction [0.0, 1.0]. Returns 0.0 if no lookups yet."""
        with self._lock:
            total = self._hits + self._misses
            return self._hits / total if total > 0 else 0.0

    def stats(self) -> dict[str, object]:
        """Return a dict of cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._store),
                "capacity": self._capacity,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }

    def __repr__(self) -> str:
        return (
            f"LRUCache(size={self.size}/{self._capacity}, "
            f"hit_rate={self.hit_rate:.1%})"
        )

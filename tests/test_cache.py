"""Tests for LRUCache."""

import threading

import pytest

from lpte.core.cache import LRUCache


class TestLRUCacheBasics:
    def test_get_miss_returns_none(self):
        cache = LRUCache(capacity=4)
        assert cache.get("missing") is None

    def test_put_and_get(self):
        cache = LRUCache(capacity=4)
        cache.put("key", "value")
        assert cache.get("key") == "value"

    def test_update_existing_key(self):
        cache = LRUCache(capacity=4)
        cache.put("k", "v1")
        cache.put("k", "v2")
        assert cache.get("k") == "v2"
        assert cache.size == 1

    def test_invalidate_existing(self):
        cache = LRUCache(capacity=4)
        cache.put("k", "v")
        assert cache.invalidate("k") is True
        assert cache.get("k") is None

    def test_invalidate_missing_returns_false(self):
        cache = LRUCache(capacity=4)
        assert cache.invalidate("nope") is False

    def test_clear_empties_cache(self):
        cache = LRUCache(capacity=4)
        cache.put("a", 1); cache.put("b", 2)
        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0


class TestLRUEviction:
    def test_evicts_lru_entry_when_over_capacity(self):
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # should evict "a" (oldest)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_access_refreshes_recency(self):
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.get("a")     # "a" now most recently used
        cache.put("d", 4)  # should evict "b" (now the oldest)
        assert cache.get("a") == 1   # still alive
        assert cache.get("b") is None  # evicted

    def test_capacity_1_always_evicts_on_new_put(self):
        cache = LRUCache(capacity=1)
        cache.put("x", 10)
        cache.put("y", 20)
        assert cache.get("x") is None
        assert cache.get("y") == 20


class TestLRUStats:
    def test_hit_miss_counting(self):
        cache = LRUCache(capacity=4)
        cache.put("k", "v")
        cache.get("k")      # hit
        cache.get("k")      # hit
        cache.get("nope")   # miss
        assert cache.hits == 2
        assert cache.misses == 1

    def test_hit_rate_empty(self):
        cache = LRUCache(capacity=4)
        assert cache.hit_rate == 0.0

    def test_hit_rate_all_hits(self):
        cache = LRUCache(capacity=4)
        cache.put("k", "v")
        cache.get("k"); cache.get("k")
        assert cache.hit_rate == 1.0

    def test_stats_dict_keys(self):
        cache = LRUCache(capacity=4)
        s = cache.stats()
        assert "size" in s and "capacity" in s and "hits" in s and "misses" in s and "hit_rate" in s

    def test_invalid_capacity_raises(self):
        with pytest.raises(ValueError):
            LRUCache(capacity=0)


class TestLRUThreadSafety:
    def test_concurrent_put_and_get(self):
        """Run many concurrent puts/gets to surface race conditions."""
        cache = LRUCache(capacity=64)
        errors = []

        def worker(tid):
            try:
                for i in range(200):
                    cache.put(f"k-{tid}-{i}", i)
                    cache.get(f"k-{tid}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
        for th in threads: th.start()
        for th in threads: th.join()

        assert not errors, f"Thread-safety errors: {errors}"
        assert cache.size <= 64  # must respect capacity

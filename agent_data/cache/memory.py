"""
In-memory cache implementation.
"""

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, Optional

from agent_data.cache.base import BaseCache


class CacheEntry:
    """Cache entry with TTL support."""

    def __init__(self, value: Any, ttl: Optional[int] = None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    @property
    def age(self) -> float:
        return time.time() - self.created_at


class MemoryCache(BaseCache):
    """In-memory cache with TTL support."""

    def __init__(self, max_size: int = 10000):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._cache[key]
                return None
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            if len(self._cache) >= self._max_size:
                await self._evict()
            self._cache[key] = CacheEntry(value, ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._cache[key]
                return False
            return True

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def size(self) -> int:
        async with self._lock:
            return len(self._cache)

    async def _evict(self) -> None:
        """Evict expired entries first, then oldest entries."""
        # Remove expired entries
        expired_keys = [
            k for k, v in self._cache.items() if v.is_expired
        ]
        for key in expired_keys:
            del self._cache[key]

        # If still over limit, remove oldest entries
        if len(self._cache) >= self._max_size:
            sorted_entries = sorted(
                self._cache.items(), key=lambda x: x[1].created_at
            )
            to_remove = len(self._cache) - self._max_size + 1
            for key, _ in sorted_entries[:to_remove]:
                del self._cache[key]

    @staticmethod
    def generate_key(*args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_parts = [str(a) for a in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    @staticmethod
    def generate_query_key(query_dict: Dict[str, Any]) -> str:
        """Generate a cache key from a query dictionary."""
        json_str = json.dumps(query_dict, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()
"""Query result caching for NL2SQL pipeline.

Wraps the existing MemoryCache with NL2SQL-specific defaults:
- TTL-based expiry (default 300s)
- LRU eviction (default max_size=1000)
- MD5 key generation from question + schema hash
"""
import hashlib
import json
from typing import Any, Dict, Optional

from agent_data.cache.memory import MemoryCache


class QueryCache:
    """NL2SQL query result cache.

    Caches (question + schema_hash) → SQL generation result to avoid
    repeated LLM calls for identical queries.
    """

    def __init__(self, ttl: int = 300, max_size: int = 1000):
        """Initialize cache.

        Args:
            ttl: Time-to-live in seconds. Set to 0 to disable caching.
            max_size: Maximum number of cached entries.
        """
        self._ttl = ttl
        self._cache = MemoryCache(max_size=max_size)

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        return await self._cache.get(key)

    async def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        await self._cache.set(key, value, ttl=self._ttl)

    async def clear(self) -> None:
        await self._cache.clear()

    async def size(self) -> int:
        return await self._cache.size()

    @staticmethod
    def generate_key(question: str, schema_hash: str, conversation_hash: str = "") -> str:
        """Generate a deterministic cache key from query parameters."""
        raw = f"{question}|{schema_hash}|{conversation_hash}"
        return hashlib.md5(raw.encode()).hexdigest()

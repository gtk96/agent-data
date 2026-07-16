"""Tests for query result caching."""
import asyncio
import pytest
from agent_data.nl2sql.cache import QueryCache


@pytest.mark.asyncio
async def test_cache_hit():
    cache = QueryCache(ttl=300)
    result = {"sql": "SELECT 1", "answer": "one"}
    await cache.set("q1", result)
    cached = await cache.get("q1")
    assert cached == result


@pytest.mark.asyncio
async def test_cache_miss():
    cache = QueryCache(ttl=300)
    cached = await cache.get("nonexistent")
    assert cached is None


@pytest.mark.asyncio
async def test_cache_ttl_expiry():
    cache = QueryCache(ttl=1)  # 1 second TTL
    await cache.set("q1", {"answer": "test"})
    # Before expiry
    cached = await cache.get("q1")
    assert cached is not None
    # Wait for expiry
    await asyncio.sleep(1.1)
    cached = await cache.get("q1")
    assert cached is None


@pytest.mark.asyncio
async def test_generate_key():
    cache = QueryCache(ttl=300)
    key1 = cache.generate_key("SELECT 1", "schema_hash_abc")
    key2 = cache.generate_key("SELECT 1", "schema_hash_abc")
    key3 = cache.generate_key("SELECT 2", "schema_hash_abc")
    assert key1 == key2  # same input = same key
    assert key1 != key3  # different input = different key


@pytest.mark.asyncio
async def test_cache_clear():
    cache = QueryCache(ttl=300)
    await cache.set("q1", {"answer": "test"})
    await cache.clear()
    assert await cache.get("q1") is None


@pytest.mark.asyncio
async def test_cache_size():
    cache = QueryCache(ttl=300, max_size=3)
    await cache.set("q1", {"answer": "1"})
    await cache.set("q2", {"answer": "2"})
    assert await cache.size() == 2
    await cache.set("q3", {"answer": "3"})
    assert await cache.size() == 3
    # Adding 4th should evict oldest
    await cache.set("q4", {"answer": "4"})
    assert await cache.size() == 3
    assert await cache.get("q1") is None  # evicted


@pytest.mark.asyncio
async def test_disabled_cache():
    cache = QueryCache(ttl=0)  # ttl=0 means disabled
    await cache.set("q1", {"answer": "test"})
    cached = await cache.get("query:SELECT 1")
    assert cached is None  # should not cache

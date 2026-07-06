"""
Basic tests for Agent Data framework.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_data import (
    AgentDataClient,
    DataSource,
    DataSourceConfig,
    DataSourceType,
    Query,
    QueryFilter,
    QueryType,
    AgentContext,
)
from agent_data.cache.memory import MemoryCache
from agent_data.tracing.memory import MemoryTracer


def run_async(coro):
    """Helper to run async functions in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_client_creation():
    """Test client creation."""
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="test_db",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
            description="Test database",
            tags=["test"],
        ),
    ]
    client = AgentDataClient(
        data_sources=data_sources,
        cache_enabled=True,
        trace_enabled=True,
    )

    assert client is not None
    assert len(client.data_sources) == 1
    assert "test_db" in client.data_sources


def test_sql_query():
    """Test SQL query execution."""
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
        ),
    ]
    client = AgentDataClient(data_sources=data_sources)

    async def _test():
        # Setup
        connector = await client._get_connector("users")
        connector._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """
        )
        connector._connection.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))

        # Query
        result = await client.query(Query(source="users", query_type=QueryType.SELECT))

        assert result.error is None
        assert len(result.data) == 1
        assert result.data[0]["name"] == "Alice"

    run_async(_test())


def test_query_with_filters():
    """Test query with filters."""
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
        ),
    ]
    client = AgentDataClient(data_sources=data_sources)

    async def _test():
        connector = await client._get_connector("users")
        connector._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                status TEXT
            )
        """
        )
        connector._connection.execute(
            "INSERT INTO users (name, status) VALUES (?, ?)", ("Alice", "active")
        )
        connector._connection.execute(
            "INSERT INTO users (name, status) VALUES (?, ?)", ("Bob", "inactive")
        )

        # Query with filter
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
                filters=[QueryFilter(field="status", operator="eq", value="active")],
            )
        )

        assert result.error is None
        assert len(result.data) == 1
        assert result.data[0]["name"] == "Alice"

    run_async(_test())


def test_cache():
    """Test caching."""
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
        ),
    ]
    client = AgentDataClient(data_sources=data_sources, cache_enabled=True)

    async def _test():
        connector = await client._get_connector("users")
        connector._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """
        )
        connector._connection.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))

        # First query
        result1 = await client.query(Query(source="users", query_type=QueryType.SELECT))

        # Second query (should be cached)
        result2 = await client.query(Query(source="users", query_type=QueryType.SELECT))

        assert result1.cached is False
        assert result2.cached is True
        assert result1.data == result2.data

    run_async(_test())


def test_health_check():
    """Test health check."""
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="test_db",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
        ),
    ]
    client = AgentDataClient(data_sources=data_sources)

    async def _test():
        connector = await client._get_connector("test_db")
        health = await client.health_check()
        assert "test_db" in health
        assert health["test_db"] is True

    run_async(_test())


def test_context():
    """Test agent context."""
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
        ),
    ]
    client = AgentDataClient(data_sources=data_sources)

    async def _test():
        context = AgentContext(
            agent_id="test_agent",
            session_id="session_123",
            user_id="user_456",
        )

        connector = await client._get_connector("users")
        connector._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """
        )
        connector._connection.execute("INSERT INTO users (name) VALUES (?)", ("Alice",))

        result = await client.query(
            Query(source="users", query_type=QueryType.SELECT),
            context=context,
        )

        assert result.error is None
        assert len(result.data) == 1

    run_async(_test())


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])

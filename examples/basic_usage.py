"""
Basic usage example for Agent Data framework.
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


async def main():
    """Basic usage example."""
    print("=== Agent Data Framework - Basic Usage ===\n")

    # Create data sources
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection=":memory:",  # In-memory SQLite
            ),
            description="User database",
            tags=["user", "profile"],
        ),
        DataSource(
            config=DataSourceConfig(
                name="products",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
            description="Product database",
            tags=["product", "catalog"],
        ),
    ]

    # Create client
    client = AgentDataClient(
        data_sources=data_sources,
        cache_enabled=True,
        trace_enabled=True,
    )

    try:
        # Connect to data sources
        print("1. Connecting to data sources...")
        for ds in data_sources:
            connector = await client._get_connector(ds.name)
            print(f"   Connected to: {ds.name}")

        # Create tables and insert test data
        print("\n2. Setting up test data...")
        connector = await client._get_connector("users")
        connector._connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                status TEXT
            )
        """)
        connector._connection.execute(
            "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
            ("Alice", "alice@example.com", "active"),
        )
        connector._connection.execute(
            "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
            ("Bob", "bob@example.com", "active"),
        )
        connector._connection.execute(
            "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
            ("Charlie", "charlie@example.com", "inactive"),
        )

        # Simple query
        print("\n3. Executing simple query...")
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
            )
        )
        print(f"   All users: {result.data}")
        print(f"   Query time: {result.query_time_ms:.2f}ms")

        # Query with filters
        print("\n4. Query with filters...")
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
                filters=[
                    QueryFilter(field="status", operator="eq", value="active")
                ],
            )
        )
        print(f"   Active users: {result.data}")

        # Natural language query
        print("\n5. Natural language query...")
        result = await client.query(
            "获取所有用户",
            context=AgentContext(agent_id="demo_agent"),
        )
        print(f"   Query result: {result.data}")

        # Batch queries
        print("\n6. Batch queries...")
        results = await client.batch_query(
            queries=[
                "获取所有用户",
                "获取所有产品",
            ],
            parallel=True,
        )
        for i, res in enumerate(results):
            print(f"   Query {i+1}: {len(res.data)} results")

        # Health check
        print("\n7. Health check...")
        health = await client.health_check()
        print(f"   Health status: {health}")

        # Get data sources
        print("\n8. Data sources:")
        sources = await client.get_data_sources()
        for ds in sources:
            print(f"   - {ds.name} ({ds.type}): {ds.description}")

        # Cache test
        print("\n9. Cache test...")
        # First query (should be cached)
        result1 = await client.query(
            "获取所有用户",
            context=AgentContext(agent_id="demo_agent"),
        )
        print(f"   First query - cached: {result1.cached}")

        # Second query (should hit cache)
        result2 = await client.query(
            "获取所有用户",
            context=AgentContext(agent_id="demo_agent"),
        )
        print(f"   Second query - cached: {result2.cached}")

    finally:
        # Close client
        await client.close()
        print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
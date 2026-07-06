"""
Multi-source data access example.
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
    """Multi-source data access example."""
    print("=== Multi-source Data Access Example ===\n")

    # Define multiple data sources
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
            description="User database",
            tags=["user", "profile"],
        ),
        DataSource(
            config=DataSourceConfig(
                name="vector_store",
                type=DataSourceType.VECTOR,
                connection="memory",
                metadata={"dimension": 128},
            ),
            description="Vector store for documents",
            tags=["vector", "search"],
        ),
    ]

    # Create client with context-aware caching
    client = AgentDataClient(
        data_sources=data_sources,
        cache_enabled=True,
        cache_ttl=300,
        trace_enabled=True,
    )

    try:
        # Setup SQL database
        print("1. Setting up SQL database...")
        sql_connector = await client._get_connector("users")
        sql_connector._connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                status TEXT,
                age INTEGER
            )
        """)
        sql_connector._connection.execute(
            "INSERT INTO users (name, email, status, age) VALUES (?, ?, ?, ?)",
            ("Alice", "alice@example.com", "active", 28),
        )
        sql_connector._connection.execute(
            "INSERT INTO users (name, email, status, age) VALUES (?, ?, ?, ?)",
            ("Bob", "bob@example.com", "active", 35),
        )
        sql_connector._connection.execute(
            "INSERT INTO users (name, email, status, age) VALUES (?, ?, ?, ?)",
            ("Charlie", "charlie@example.com", "inactive", 42),
        )

        # Setup vector store
        print("2. Setting up vector store...")
        import numpy as np
        vector_connector = await client._get_connector("vector_store")
        sample_docs = [
            {"text": "Python is a programming language", "category": "programming"},
            {"text": "Machine learning uses algorithms", "category": "ai"},
            {"text": "Databases store structured data", "category": "data"},
            {"text": "Web development uses HTML/CSS/JS", "category": "web"},
        ]
        for doc in sample_docs:
            vector = np.random.randn(128).tolist()
            vector_connector.add_document(
                vector=vector,
                text=doc["text"],
                metadata={"category": doc["category"]},
            )

        # Query SQL database
        print("\n3. Querying SQL database...")
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
                filters=[
                    QueryFilter(field="status", operator="eq", value="active"),
                    QueryFilter(field="age", operator="gte", value=30),
                ],
                order_by="age",
                order_desc=True,
            )
        )
        print(f"   Active users age >= 30: {result.data}")

        # Query vector store
        print("\n4. Querying vector store...")
        result = await client.query(
            Query(
                source="vector_store",
                query_type=QueryType.SEARCH,
                limit=3,
                metadata={"vector": np.random.randn(128).tolist()},
            )
        )
        print(f"   Similar documents: {len(result.data)} found")
        for doc in result.data[:2]:
            print(f"     - {doc['text']} (score: {doc['score']:.3f})")

        # Batch queries across sources
        print("\n5. Batch queries across sources...")
        results = await client.batch_query(
            queries=[
                Query(source="users", query_type=QueryType.SELECT),
                Query(
                    source="users",
                    query_type=QueryType.SELECT,
                    filters=[QueryFilter(field="status", operator="eq", value="active")],
                ),
            ],
            parallel=True,
        )
        print(f"   All users: {len(results[0].data)}")
        print(f"   Active users: {len(results[1].data)}")

        # Context-aware query
        print("\n6. Context-aware query...")
        context = AgentContext(
            agent_id="customer_service",
            session_id="session_123",
            user_id="user_456",
            metadata={"source": "web_chat"},
        )
        result = await client.query(
            Query(source="users", query_type=QueryType.SELECT),
            context=context,
        )
        print(f"   Query with context: {len(result.data)} results")

        # Cache demonstration
        print("\n7. Cache demonstration...")
        result1 = await client.query(
            "SELECT * FROM users",
            context=AgentContext(agent_id="demo"),
        )
        print(f"   First query - cached: {result1.cached}")

        result2 = await client.query(
            "SELECT * FROM users",
            context=AgentContext(agent_id="demo"),
        )
        print(f"   Second query - cached: {result2.cached}")

        # Health check
        print("\n8. Health check...")
        health = await client.health_check()
        print(f"   Health status: {health}")

    finally:
        await client.close()
        print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
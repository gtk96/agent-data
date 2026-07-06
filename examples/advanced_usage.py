"""
Advanced usage example for Agent Data framework.
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
from agent_data.connectors.vector import InMemoryVectorConnector
import numpy as np


async def main():
    """Advanced usage example."""
    print("=== Agent Data Framework - Advanced Usage ===\n")

    # Create data sources
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

    # Create custom cache and tracer
    cache = MemoryCache(max_size=1000)
    tracer = MemoryTracer()

    # Create client
    client = AgentDataClient(
        data_sources=data_sources,
        cache_enabled=True,
        cache_ttl=600,
        trace_enabled=True,
        cache=cache,
        tracer=tracer,
    )

    try:
        # Connect and setup
        print("1. Setting up...")
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

        # Setup vector store with sample data
        vector_connector = await client._get_connector("vector_store")
        sample_docs = [
            {"text": "Python is a programming language", "category": "programming"},
            {"text": "Machine learning uses algorithms", "category": "ai"},
            {"text": "Databases store structured data", "category": "data"},
            {"text": "Web development uses HTML/CSS/JS", "category": "web"},
            {"text": "Deep learning is a subset of ML", "category": "ai"},
        ]
        for doc in sample_docs:
            vector = np.random.randn(128).tolist()
            vector_connector.add_document(
                vector=vector,
                text=doc["text"],
                metadata={"category": doc["category"]},
            )

        # SQL queries with various filters
        print("\n2. SQL Queries with filters...")

        # Range filter
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
                filters=[
                    QueryFilter(field="age", operator="gte", value=30),
                    QueryFilter(field="status", operator="eq", value="active"),
                ],
                order_by="age",
                order_desc=True,
            )
        )
        print(f"   Users age >= 30: {result.data}")

        # IN filter
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
                filters=[
                    QueryFilter(field="name", operator="in", value=["Alice", "Charlie"]),
                ],
            )
        )
        print(f"   Users named Alice or Charlie: {result.data}")

        # LIKE filter
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
                filters=[
                    QueryFilter(field="email", operator="like", value="%example%"),
                ],
            )
        )
        print(f"   Users with example.com email: {len(result.data)} found")

        # Vector similarity search
        print("\n3. Vector Similarity Search...")

        # Search with random query vector
        result = await client.query(
            Query(
                source="vector_store",
                query_type=QueryType.SEARCH,
                limit=3,
                metadata={"vector": np.random.randn(128).tolist()},
            )
        )
        print(f"   Found {len(result.data)} similar documents:")
        for doc in result.data:
            print(f"     - {doc['text']} (score: {doc['score']:.3f})")

        # Search with metadata filter
        result = await client.query(
            Query(
                source="vector_store",
                query_type=QueryType.SEARCH,
                filters=[
                    QueryFilter(field="category", operator="eq", value="ai"),
                ],
                limit=2,
                metadata={"vector": np.random.randn(128).tolist()},
            )
        )
        print(f"\n   AI category documents:")
        for doc in result.data:
            print(f"     - {doc['text']} (score: {doc['score']:.3f})")

        # Batch queries
        print("\n4. Batch queries...")
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

        # Agent context
        print("\n5. Agent context...")
        context = AgentContext(
            agent_id="demo_agent",
            session_id="session_123",
            user_id="user_456",
            metadata={"source": "web_chat"},
        )
        result = await client.query(
            Query(source="users", query_type=QueryType.SELECT),
            context=context,
        )
        print(f"   Query with context: {len(result.data)} results")

        # Check tracing
        print("\n6. Tracing...")
        trace_stats = tracer.get_stats()
        print(f"   Total traces: {trace_stats['total_traces']}")
        print(f"   Total spans: {trace_stats['total_spans']}")

        # Get all traces for debugging
        all_traces = tracer.get_all_traces()
        for trace_id, spans in list(all_traces.items())[:2]:
            print(f"\n   Trace {trace_id[:8]}...")
            for span in spans[:2]:
                print(f"     - {span['name']}: {span['duration_ms']:.2f}ms")

        # Cache statistics
        print("\n7. Cache statistics...")
        cache_size = await cache.size()
        print(f"   Cache size: {cache_size} items")

        # Schema inspection
        print("\n8. Schema inspection...")
        schema = sql_connector.get_schema()
        print(f"   Tables: {list(schema.keys())}")
        if "users" in schema:
            print(f"   Users columns: {[col['name'] for col in schema['users']['columns']]}")

        vector_schema = vector_connector.get_schema()
        print(f"   Vector store dimension: {vector_schema['dimension']}")
        print(f"   Vector store documents: {vector_schema['document_count']}")

        # Health check
        print("\n9. Health check...")
        health = await client.health_check()
        print(f"   Health status: {health}")

    finally:
        await client.close()
        print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
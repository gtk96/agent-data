"""
PostgreSQL connector example.
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
)


async def main():
    """PostgreSQL connector example."""
    print("=== PostgreSQL Connector Example ===\n")

    # Note: This example requires a running PostgreSQL instance
    # Update the connection string with your PostgreSQL credentials

    # Define PostgreSQL data source
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="users",
                type=DataSourceType.SQL,
                connection="postgresql://user:password@localhost:5432/mydb",
                metadata={
                    "min_size": 5,
                    "max_size": 20,
                },
            ),
            description="PostgreSQL user database",
            tags=["user", "postgresql"],
        ),
    ]

    # Create client
    client = AgentDataClient(
        data_sources=data_sources,
        cache_enabled=True,
        trace_enabled=True,
    )

    try:
        # Connect to PostgreSQL
        print("1. Connecting to PostgreSQL...")
        connector = await client._get_connector("users")

        # Create table (if not exists)
        print("2. Creating table...")
        async with connector._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(200) UNIQUE NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    age INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Insert sample data
        print("3. Inserting sample data...")
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.INSERT,
                metadata={
                    "data": {
                        "name": "Alice",
                        "email": "alice@example.com",
                        "status": "active",
                        "age": 28,
                    }
                },
            )
        )
        print(f"   Inserted user: {result.data}")

        # Query with filters
        print("\n4. Querying with filters...")
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SELECT,
                filters=[
                    QueryFilter(field="status", operator="eq", value="active"),
                    QueryFilter(field="age", operator="gte", value=18),
                ],
                order_by="age",
                order_desc=True,
                limit=10,
            )
        )
        print(f"   Active users: {result.data}")

        # Text search
        print("\n5. Text search...")
        result = await client.query(
            Query(
                source="users",
                query_type=QueryType.SEARCH,
                query="alice",
                limit=5,
            )
        )
        print(f"   Search results: {result.data}")

        # Get table schema
        print("\n6. Table schema...")
        columns = await connector.get_table_columns("users")
        print(f"   Columns: {columns}")

        # Get all tables
        print("\n7. All tables...")
        tables = await connector.get_tables()
        print(f"   Tables: {tables}")

        # Health check
        print("\n8. Health check...")
        health = await client.health_check()
        print(f"   Health status: {health}")

    except Exception as e:
        print(f"Error: {e}")
        print("\nNote: This example requires a running PostgreSQL instance.")
        print("Update the connection string with your PostgreSQL credentials.")

    finally:
        await client.close()
        print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
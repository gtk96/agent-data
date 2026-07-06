"""
REST API connector example.
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
    """REST API connector example."""
    print("=== REST API Connector Example ===\n")

    # Note: This example uses JSONPlaceholder (fake REST API for testing)
    # In production, replace with your actual API

    # Define REST API data source
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="jsonplaceholder",
                type=DataSourceType.API,
                connection="https://jsonplaceholder.typicode.com",
                metadata={
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "timeout": 30,
                    "health_endpoint": "/posts/1",  # Simple health check
                },
            ),
            description="JSONPlaceholder API",
            tags=["api", "rest", "testing"],
        ),
    ]

    # Create client
    client = AgentDataClient(
        data_sources=data_sources,
        cache_enabled=True,
        cache_ttl=60,
        trace_enabled=True,
    )

    try:
        # Connect to API
        print("1. Connecting to API...")
        connector = await client._get_connector("jsonplaceholder")

        # GET request - fetch posts
        print("\n2. Fetching posts...")
        result = await client.query(
            Query(
                source="jsonplaceholder",
                query_type=QueryType.SELECT,
                metadata={
                    "endpoint": "/posts",
                    "method": "GET",
                    "params": {"_limit": 5},
                },
            )
        )
        print(f"   Fetched {len(result.data)} posts")
        if result.data:
            print(f"   First post: {result.data[0]['title'][:50]}...")

        # GET request with path parameter
        print("\n3. Fetching single post...")
        result = await client.query(
            Query(
                source="jsonplaceholder",
                query_type=QueryType.SELECT,
                metadata={
                    "endpoint": "/posts/1",
                    "method": "GET",
                },
            )
        )
        print(f"   Post: {result.data[0]['title'] if result.data else 'Not found'}")

        # GET request with filters (client-side)
        print("\n4. Filtering posts...")
        result = await client.query(
            Query(
                source="jsonplaceholder",
                query_type=QueryType.SELECT,
                metadata={
                    "endpoint": "/posts",
                    "method": "GET",
                },
                filters=[
                    QueryFilter(field="userId", operator="eq", value=1),
                ],
                limit=3,
            )
        )
        print(f"   User 1 posts: {len(result.data)}")

        # POST request - create new post
        print("\n5. Creating new post...")
        result = await client.query(
            Query(
                source="jsonplaceholder",
                query_type=QueryType.INSERT,
                metadata={
                    "endpoint": "/posts",
                    "method": "POST",
                    "body": {
                        "title": "New Post",
                        "body": "This is a new post created via Agent Data framework",
                        "userId": 1,
                    },
                },
            )
        )
        print(f"   Created post: {result.data}")

        # GET request - fetch users
        print("\n6. Fetching users...")
        result = await client.query(
            Query(
                source="jsonplaceholder",
                query_type=QueryType.SELECT,
                metadata={
                    "endpoint": "/users",
                    "method": "GET",
                },
                limit=3,
            )
        )
        print(f"   Users: {len(result.data)}")
        if result.data:
            print(f"   First user: {result.data[0]['name']}")

        # Convenience methods
        print("\n7. Using convenience methods...")
        result = await connector.get("/comments", params={"postId": 1, "_limit": 2})
        print(f"   Comments: {len(result.data)}")

        # Health check
        print("\n8. Health check...")
        health = await client.health_check()
        print(f"   Health status: {health}")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        await client.close()
        print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
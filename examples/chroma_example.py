"""
Chroma vector store example.
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
import numpy as np


async def main():
    """Chroma vector store example."""
    print("=== Chroma Vector Store Example ===\n")

    # Note: This example requires chromadb
    # Install with: pip install chromadb

    # Define Chroma data source
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="documents",
                type=DataSourceType.VECTOR,
                connection="chroma",
                metadata={
                    "collection": "my_documents",
                    "persist_directory": "./chroma_data",  # Optional: for persistence
                },
            ),
            description="Document vector store",
            tags=["vector", "chroma", "documents"],
        ),
    ]

    # Create client
    client = AgentDataClient(
        data_sources=data_sources,
        cache_enabled=False,  # Disable cache for vector search
        trace_enabled=True,
    )

    try:
        # Connect to Chroma
        print("1. Connecting to Chroma...")
        connector = await client._get_connector("documents")

        # Sample documents
        documents = [
            {"text": "Python is a programming language", "category": "programming", "language": "python"},
            {"text": "JavaScript is used for web development", "category": "programming", "language": "javascript"},
            {"text": "Machine learning uses algorithms", "category": "ai", "topic": "ml"},
            {"text": "Deep learning is a subset of ML", "category": "ai", "topic": "dl"},
            {"text": "Databases store structured data", "category": "data", "type": "sql"},
            {"text": "Vector databases store embeddings", "category": "data", "type": "vector"},
        ]

        # Add documents
        print("2. Adding documents...")
        for i, doc in enumerate(documents):
            embedding = np.random.randn(384).tolist()  # Random embedding for demo
            result = await client.query(
                Query(
                    source="documents",
                    query_type=QueryType.INSERT,
                    metadata={
                        "documents": [doc["text"]],
                        "ids": [f"doc_{i}"],
                        "metadatas": [{"category": doc["category"], "language": doc.get("language"), "topic": doc.get("topic"), "type": doc.get("type")}],
                        "embeddings": [embedding],
                    },
                )
            )
        print(f"   Added {len(documents)} documents")

        # Similarity search
        print("\n3. Similarity search...")
        result = await client.query(
            Query(
                source="documents",
                query_type=QueryType.SEARCH,
                query="programming",
                limit=3,
            )
        )
        print(f"   Found {len(result.data)} similar documents:")
        for doc in result.data:
            print(f"     - {doc['text']} (score: {doc['score']:.3f})")

        # Filtered search
        print("\n4. Filtered search...")
        result = await client.query(
            Query(
                source="documents",
                query_type=QueryType.SEARCH,
                query="data",
                filters=[
                    QueryFilter(field="category", operator="eq", value="data"),
                ],
                limit=2,
            )
        )
        print(f"   Data category documents:")
        for doc in result.data:
            print(f"     - {doc['text']} (score: {doc['score']:.3f})")

        # Get all documents
        print("\n5. Get all documents...")
        result = await client.query(
            Query(
                source="documents",
                query_type=QueryType.SELECT,
                limit=10,
            )
        )
        print(f"   Total documents: {len(result.data)}")

        # Get collection info
        print("\n6. Collection info...")
        info = await connector.get_collection_info()
        print(f"   Collection: {info}")

        # Health check
        print("\n7. Health check...")
        health = await client.health_check()
        print(f"   Health status: {health}")

    except ImportError as e:
        print(f"Error: {e}")
        print("\nNote: This example requires chromadb.")
        print("Install with: pip install chromadb")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        await client.close()
        print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
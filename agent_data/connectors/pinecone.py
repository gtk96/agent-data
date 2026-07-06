"""
Pinecone vector store connector.
"""

import time
from typing import Any, Dict, List, Optional

from agent_data.core.connector import BaseConnector
from agent_data.core.models import (
    DataSourceConfig,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)


class PineconeConnector(BaseConnector):
    """Pinecone vector store connector."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._client = None
        self._index = None
        self._index_name = config.metadata.get("index", "default")
        self._api_key = config.metadata.get("api_key", "")
        self._environment = config.metadata.get("environment", "us-east-1")

    async def connect(self) -> None:
        """Establish connection to Pinecone."""
        try:
            from pinecone import Pinecone

            self._client = Pinecone(api_key=self._api_key)
            self._index = self._client.Index(self._index_name)
            self._connected = True
        except ImportError:
            raise ImportError(
                "pinecone-client is required for Pinecone connector. "
                "Install it with: pip install pinecone-client"
            )

    async def disconnect(self) -> None:
        """Close Pinecone connection."""
        self._client = None
        self._index = None
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a Pinecone query."""
        if not self._connected or not self._index:
            raise RuntimeError("Not connected to Pinecone")

        start_time = time.time()

        try:
            if query.query_type == QueryType.SEARCH:
                return await self._similarity_search(query)
            elif query.query_type == QueryType.INSERT:
                return await self._upsert(query)
            elif query.query_type == QueryType.DELETE:
                return await self._delete(query)
            elif query.query_type == QueryType.SELECT:
                return await self._fetch(query)
            else:
                return QueryResult(
                    source=self.name,
                    error=f"Unsupported query type: {query.query_type}",
                    query_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            return QueryResult(
                source=self.name,
                error=str(e),
                query_time_ms=(time.time() - start_time) * 1000,
            )

    async def _similarity_search(self, query: Query) -> QueryResult:
        """Perform similarity search."""
        query_vector = query.metadata.get("vector", None)
        n_results = query.limit or 10

        # Build filter
        pinecone_filter = self._build_filter(query.filters)

        if query_vector:
            results = self._index.query(
                vector=query_vector,
                top_k=n_results,
                include_metadata=True,
                filter=pinecone_filter,
            )
        else:
            return QueryResult(
                source=self.name,
                error="No query vector provided",
                query_time_ms=0,
            )

        # Format results
        data = []
        for match in results.get("matches", []):
            item = {
                "id": match.get("id"),
                "score": match.get("score"),
                "metadata": match.get("metadata", {}),
            }
            data.append(item)

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"index": self._index_name},
        )

    async def _upsert(self, query: Query) -> QueryResult:
        """Upsert vectors."""
        vectors = query.metadata.get("vectors", [])

        if not vectors:
            # Single vector upsert
            vector_id = query.metadata.get("id")
            vector = query.metadata.get("vector")
            metadata = query.metadata.get("metadata", {})

            if vector_id and vector:
                vectors = [{"id": vector_id, "values": vector, "metadata": metadata}]

        if not vectors:
            return QueryResult(
                source=self.name,
                error="No vectors provided for upsert",
            )

        # Format vectors for Pinecone
        formatted_vectors = []
        for v in vectors:
            formatted_vectors.append({
                "id": v["id"],
                "values": v["vector"],
                "metadata": v.get("metadata", {}),
            })

        self._index.upsert(vectors=formatted_vectors)

        return QueryResult(
            data=[{"id": v["id"]} for v in vectors],
            source=self.name,
            metadata={"upserted_count": len(vectors)},
        )

    async def _delete(self, query: Query) -> QueryResult:
        """Delete vectors."""
        ids = query.metadata.get("ids", [])

        if ids:
            self._index.delete(ids=ids)
            deleted_count = len(ids)
        else:
            # Delete by filter
            pinecone_filter = self._build_filter(query.filters)
            if pinecone_filter:
                self._index.delete(filter=pinecone_filter)
                deleted_count = -1
            else:
                return QueryResult(
                    source=self.name,
                    error="No IDs or filters provided for deletion",
                )

        return QueryResult(
            data=[{"deleted_count": deleted_count}],
            source=self.name,
            metadata={"deleted_count": deleted_count},
        )

    async def _fetch(self, query: Query) -> QueryResult:
        """Fetch vectors by ID."""
        ids = query.metadata.get("ids", [])

        if not ids:
            return QueryResult(
                source=self.name,
                error="No IDs provided for fetch",
            )

        results = self._index.fetch(ids=ids)

        data = []
        for vector_id, vector_data in results.get("vectors", {}).items():
            item = {
                "id": vector_id,
                "metadata": vector_data.get("metadata", {}),
            }
            data.append(item)

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"index": self._index_name},
        )

    def _build_filter(self, filters: List[QueryFilter]) -> Optional[Dict]:
        """Build Pinecone filter from QueryFilter list."""
        if not filters:
            return None

        conditions = {}
        for f in filters:
            if f.operator == "eq":
                conditions[f.field] = {"$eq": f.value}
            elif f.operator == "ne":
                conditions[f.field] = {"$ne": f.value}
            elif f.operator == "gt":
                conditions[f.field] = {"$gt": f.value}
            elif f.operator == "gte":
                conditions[f.field] = {"$gte": f.value}
            elif f.operator == "lt":
                conditions[f.field] = {"$lt": f.value}
            elif f.operator == "lte":
                conditions[f.field] = {"$lte": f.value}
            elif f.operator == "in":
                conditions[f.field] = {"$in": f.value}

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions

        return {"$and": [{k: v} for k, v in conditions.items()]}

    async def health_check(self) -> bool:
        """Check Pinecone health."""
        try:
            stats = self._index.describe_index_stats()
            return stats is not None
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get Pinecone schema."""
        return {
            "type": "pinecone",
            "index": self._index_name,
            "environment": self._environment,
        }
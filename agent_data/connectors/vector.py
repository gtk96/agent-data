"""
In-memory vector store connector for development and testing.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import numpy as np

from agent_data.core.connector import BaseConnector
from agent_data.core.models import (
    DataSourceConfig,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)


class InMemoryVectorConnector(BaseConnector):
    """In-memory vector store connector for development and testing."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._vectors: Dict[str, Dict[str, Any]] = {}
        self._dimension: int = config.metadata.get("dimension", 128)
        # Shared mutable state requires a lock — reads and writes can race
        # under concurrent asyncio.gather / batch_query.
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize vector store."""
        self._connected = True

    async def disconnect(self) -> None:
        """Clear vector store."""
        async with self._lock:
            self._vectors.clear()
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a vector query."""
        start_time = time.time()

        try:
            if query.query_type == QueryType.SEARCH:
                return await self._similarity_search(query)
            elif query.query_type == QueryType.INSERT:
                return await self._insert_vectors(query)
            elif query.query_type == QueryType.DELETE:
                return await self._delete_vectors(query)
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
        # Get query vector
        query_vector = query.metadata.get("vector")
        if query_vector is None:
            # Generate a random vector for demo purposes
            query_vector = np.random.randn(self._dimension).tolist()

        query_vector = np.array(query_vector)

        # Snapshot vectors under the lock, then do math outside it to keep the
        # critical section short.
        async with self._lock:
            snapshot = list(self._vectors.items())

        # Calculate similarities
        scores = []
        for doc_id, doc_data in snapshot:
            doc_vector = np.array(doc_data["vector"])
            similarity = self._cosine_similarity(query_vector, doc_vector)

            # Apply filters
            if self._matches_filters(doc_data.get("metadata", {}), query.filters):
                scores.append((doc_id, similarity, doc_data))

        # Sort by similarity (descending)
        scores.sort(key=lambda x: x[1], reverse=True)

        # Apply limit
        limit = query.limit or 10
        scores = scores[:limit]

        # Build results
        data = []
        for doc_id, score, doc_data in scores:
            result_item = {
                "id": doc_id,
                "score": float(score),
                "text": doc_data.get("text", ""),
                "metadata": doc_data.get("metadata", {}),
            }
            data.append(result_item)

        return QueryResult(
            data=data,
            total_count=len(scores),
            source=self.name,
            metadata={"query_vector": query_vector.tolist()},
        )

    async def _insert_vectors(self, query: Query) -> QueryResult:
        """Insert vectors into the store."""
        vectors_data = query.metadata.get("vectors", [])
        if not vectors_data:
            # Check for single vector insertion
            if "vector" in query.metadata and "text" in query.metadata:
                vectors_data = [
                    {
                        "vector": query.metadata["vector"],
                        "text": query.metadata["text"],
                        "metadata": query.metadata.get("metadata", {}),
                    }
                ]

        inserted_ids = []
        async with self._lock:
            for item in vectors_data:
                doc_id = item.get("id", str(uuid.uuid4()))
                self._vectors[doc_id] = {
                    "vector": item["vector"],
                    "text": item.get("text", ""),
                    "metadata": item.get("metadata", {}),
                }
                inserted_ids.append(doc_id)

        return QueryResult(
            data=[{"id": doc_id} for doc_id in inserted_ids],
            source=self.name,
            metadata={"inserted_count": len(inserted_ids)},
        )

    async def _delete_vectors(self, query: Query) -> QueryResult:
        """Delete vectors from the store."""
        ids_to_delete = query.metadata.get("ids", [])

        deleted_count = 0
        async with self._lock:
            for doc_id in ids_to_delete:
                if doc_id in self._vectors:
                    del self._vectors[doc_id]
                    deleted_count += 1

        return QueryResult(
            data=[{"deleted_count": deleted_count}],
            source=self.name,
            metadata={"deleted_count": deleted_count},
        )

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _matches_filters(self, metadata: Dict[str, Any], filters: List[QueryFilter]) -> bool:
        """Check if metadata matches all filters."""
        for f in filters:
            value = metadata.get(f.field)
            if value is None:
                return False

            if f.operator == "eq" and value != f.value:
                return False
            elif f.operator == "ne" and value == f.value:
                return False
            elif f.operator == "gt" and value <= f.value:
                return False
            elif f.operator == "lt" and value >= f.value:
                return False
            elif f.operator == "gte" and value < f.value:
                return False
            elif f.operator == "lte" and value > f.value:
                return False
            elif f.operator == "in" and value not in f.value:
                return False
            elif f.operator == "like" and f.value not in str(value):
                return False

        return True

    async def health_check(self) -> bool:
        """Check if vector store is healthy."""
        return self._connected

    def get_schema(self) -> Dict[str, Any]:
        """Get vector store schema."""
        return {
            "dimension": self._dimension,
            "document_count": len(self._vectors),
            "supports_similarity_search": True,
            "supports_metadata_filters": True,
        }

    def add_document(
        self,
        vector: List[float],
        text: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """Add a document to the vector store (convenience method, sync).

        Note: this method does not acquire self._lock because it is synchronous
        and intended for single-threaded setup. Concurrent async writers must
        use execute(Query(..., query_type=QueryType.INSERT)).
        """
        doc_id = doc_id or str(uuid.uuid4())
        self._vectors[doc_id] = {
            "vector": vector,
            "text": text,
            "metadata": metadata or {},
        }
        return doc_id

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID (sync, single-threaded use)."""
        return self._vectors.get(doc_id)
